"""Stage 8: knowledge fusion — blocking, layered matching, deterministic merge, review queue.
An erroneous merge is worse than a missed one: auto-merge only above the high threshold."""
from __future__ import annotations

import itertools
import re

from .schema import Ontology
from .store import Store, norm

AUTO = 0.90
REVIEW = 0.60
HARD_KEYS = ("cas_number", "sku", "pmid", "doi")  # attribute layer: equal -> strong match; both set and different -> reject


def tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if t}


def _keys(n: dict) -> set[str]:
    return {norm(n["name"])} | {norm(a) for a in n["aliases"]}


def score_pair(store: Store, a: dict, b: dict) -> tuple[float, list[str]]:
    reasons: list[str] = []
    # attribute layer: hard identifiers
    for k in HARD_KEYS:
        av, bv = a["attrs"].get(k), b["attrs"].get(k)
        if av and bv:
            if norm(av) == norm(bv):
                return 0.98, [f"identical {k}"]
            return 0.0, [f"different {k}"]
    # string layer
    ka, kb = _keys(a), _keys(b)
    if ka & kb:
        reasons.append("alias/name key match")
        s = 0.95
    elif any(len(x) >= 5 and (x in y or y in x) for x in ka for y in kb):
        reasons.append("key containment")   # needs structure evidence to reach auto-merge
        s = 0.80
    else:
        ta, tb = tokens(a["name"]), tokens(b["name"])
        j = len(ta & tb) / max(1, len(ta | tb))
        s = 0.55 * j
        if j:
            reasons.append(f"token jaccard {j:.2f}")
    # structure layer: shared neighbourhood
    na = {(e["rel"], e["dst"] if e["src"] == a["id"] else e["src"]) for e in store.edges(a["id"])}
    nb = {(e["rel"], e["dst"] if e["src"] == b["id"] else e["src"]) for e in store.edges(b["id"])}
    if na and nb:
        shared = len(na & nb) / max(1, min(len(na), len(nb)))
        if shared:
            s += 0.3 * shared
            reasons.append(f"shared neighbours {shared:.2f}")
    return min(s, 0.97), reasons


def blocks(store: Store, type_: str):
    """Cheap candidate generation: same type AND (shared key/alias OR shared name token)."""
    nodes = store.nodes(type_)
    by_key: dict[str, set[str]] = {}
    for n in nodes:
        for k in _keys(n) | {t for t in tokens(n["name"]) if len(t) > 2}:
            by_key.setdefault(k, set()).add(n["id"])
    pairs = set()
    for ids in by_key.values():
        if 1 < len(ids) <= 50:
            for a, b in itertools.combinations(sorted(ids), 2):
                pairs.add((a, b))
    return nodes, pairs


def merge(store: Store, keep_id: str, drop_id: str) -> None:
    """Deterministic merge policy: keep canonical name of `keep`, union aliases, re-point edges,
    keep conflicting attribute values per source, record merged_from for undo."""
    keep, drop = store.get(keep_id), store.get(drop_id)
    if not keep or not drop or keep_id == drop_id:
        return
    attrs, conflicts = dict(keep["attrs"]), dict(keep["conflicts"])
    for k, v in drop["attrs"].items():
        if k not in attrs:
            attrs[k] = v
        elif attrs[k] != v:
            conflicts.setdefault(k, [{"value": attrs[k], "source": keep["source"]}])
            conflicts[k].append({"value": v, "source": drop["source"]})
    aliases = sorted((set(keep["aliases"]) | set(drop["aliases"]) | {drop["name"]}) - {keep["name"]})
    store.update_node_raw(keep_id, attrs=attrs, conflicts=conflicts, aliases=aliases,
                          merged_from=keep["merged_from"] + [{"id": drop_id, "name": drop["name"], "source": drop["source"]}])
    store._index_aliases(keep_id, aliases)
    for e in store.edges(drop_id):
        src = keep_id if e["src"] == drop_id else e["src"]
        dst = keep_id if e["dst"] == drop_id else e["dst"]
        if src != dst:
            store.add_edge(src, e["rel"], dst, e["attrs"], e["source"], e["confidence"], e.get("evidence"),
                           e.get("valid_from"), e.get("valid_to"))
    store.delete_node(drop_id)


def run(store: Store, onto: Ontology, apply: bool = False, auto: float = AUTO, review: float = REVIEW) -> dict:
    report = {"auto": [], "review": [], "rejected": 0}
    for t in onto.types():
        nodes, pairs = blocks(store, t)
        by_id = {n["id"]: n for n in nodes}
        for a_id, b_id in sorted(pairs):
            a, b = by_id.get(a_id), by_id.get(b_id)
            if not a or not b or store.get(a_id) is None or store.get(b_id) is None:
                continue
            s, reasons = score_pair(store, a, b)
            if s >= auto:
                keep, drop = (a, b) if (a["confidence"] == "high") >= (b["confidence"] == "high") else (b, a)
                report["auto"].append((keep["id"], drop["id"], s, reasons))
                if apply:
                    merge(store, keep["id"], drop["id"])
            elif s >= review:
                report["review"].append((a_id, b_id, s, reasons))
                store.enqueue_review(a_id, b_id, s, reasons)
            else:
                report["rejected"] += 1
    store.commit()
    return report
