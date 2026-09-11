"""Stages 4-6 for STRUCTURED sources: direct mapping from seed YAML to the graph (no NLP).
Two passes — all nodes first, then edges — so edges can only reference entities that exist."""
from __future__ import annotations

from pathlib import Path

import yaml

from .schema import Ontology
from .store import ROOT, Store, parse_ref

SEEDS_DIR = ROOT / "seeds"


def load_seed_files(seeds_dir: Path = SEEDS_DIR) -> list[dict]:
    docs = []
    for p in sorted(seeds_dir.glob("*.yaml")):
        data = yaml.safe_load(p.read_text()) or {}
        if "type" not in data or "items" not in data:
            raise ValueError(f"{p}: seed file needs top-level 'type' and 'items'")
        data.setdefault("source", str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p))
        data.setdefault("confidence", "medium")
        docs.append(data)
    return docs


def ingest(store: Store, onto: Ontology, seeds_dir: Path = SEEDS_DIR, strict: bool = True) -> dict:
    docs = load_seed_files(seeds_dir)
    stats = {"nodes": 0, "edges": 0, "warnings": [], "errors": []}
    # pass 1: nodes
    for d in docs:
        t = d["type"]
        if not onto.has_type(t):
            stats["errors"].append(f"{d['source']}: unknown type {t}")
            continue
        for it in d["items"]:
            attrs = it.get("attrs", {}) or {}
            for w in onto.check_node(t, attrs):
                stats["warnings"].append(f"{d['source']} {it['name']}: {w}")
            store.upsert_node(t, it["name"], attrs, it.get("aliases", []) or [],
                              source=it.get("source", d["source"]),
                              confidence=it.get("confidence", d["confidence"]),
                              valid_from=it.get("valid_from"), valid_to=it.get("valid_to"))
            stats["nodes"] += 1
    # pass 2: edges (domain/range validated; never create endpoints)
    for d in docs:
        t = d["type"]
        for it in d["items"]:
            src = store.resolve(t, it["name"])
            if src is None:
                continue
            for e in it.get("edges", []) or []:
                tt, tn = parse_ref(e["to"])
                dst = store.resolve(tt, tn)
                if dst is None:
                    stats["errors"].append(f"{d['source']} {it['name']} -{e['rel']}-> {e['to']}: target not found")
                    continue
                err = onto.check_edge(e["rel"], src["type"], dst["type"])
                if err:
                    stats["errors"].append(f"{d['source']} {it['name']} -{e['rel']}-> {e['to']}: {err}")
                    continue
                store.add_edge(src["id"], e["rel"], dst["id"], e.get("attrs", {}) or {},
                               source=e.get("source", it.get("source", d["source"])),
                               confidence=e.get("confidence", it.get("confidence", d["confidence"])),
                               evidence=e.get("evidence"), valid_from=e.get("valid_from"), valid_to=e.get("valid_to"))
                stats["edges"] += 1
    if strict and stats["errors"]:
        store.conn.rollback()
    else:
        store.commit()
    return stats


def ingest_staged(store: Store, onto: Ontology, rows: list[dict]) -> dict:
    """Move accepted staging rows (from kg extract) into the graph. Nodes first, then edges."""
    stats = {"nodes": 0, "edges": 0, "errors": []}
    for r in [r for r in rows if r["kind"] == "node"]:
        p = r["payload"]
        store.upsert_node(p["type"], p["canonical"], p.get("attrs", {}), p.get("aliases", []),
                          source=r["source"], confidence=r["confidence"] or "medium")
        stats["nodes"] += 1
    for r in [r for r in rows if r["kind"] == "edge"]:
        p = r["payload"]
        st, sn = parse_ref(p["src"]); dt_, dn = parse_ref(p["dst"])
        s, d = store.resolve(st, sn), store.resolve(dt_, dn)
        if not s or not d:
            stats["errors"].append(f"staging {r['id']}: endpoint missing ({p['src']} / {p['dst']})")
            continue
        err = onto.check_edge(p["rel"], s["type"], d["type"])
        if err:
            stats["errors"].append(f"staging {r['id']}: {err}")
            continue
        store.add_edge(s["id"], p["rel"], d["id"], p.get("attrs", {}), source=r["source"],
                       confidence=r["confidence"] or "medium", evidence=r.get("evidence"))
        stats["edges"] += 1
    store.commit()
    return stats
