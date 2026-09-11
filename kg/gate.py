"""Stage 7: quality gate over staged extractions. Sample, score, fix the PROMPT not the output,
re-run. Nothing enters the graph below the precision bar."""
from __future__ import annotations

import random

from .ingest import ingest_staged
from .schema import Ontology
from .store import Store

PRECISION_BAR = 0.90
MIN_SCORED = 20


def sample(store: Store, n: int = 50, seed: int = 0) -> list[dict]:
    rows = store.staging_rows("pending")
    random.Random(seed).shuffle(rows)
    return sorted(rows[:n], key=lambda r: r["id"])


def fmt_row(r: dict) -> str:
    p = r["payload"]
    if r["kind"] == "node":
        head = f"{p['type']}:{p['canonical']}" + (f" (surface '{p['surface']}')" if p.get("surface") != p["canonical"] else "")
        if p.get("resolved_to"):
            head += f" -> existing {p['resolved_to']}"
        if p.get("attrs"):
            head += f" {p['attrs']}"
    else:
        head = f"{p['src']} -{p['rel']}-> {p['dst']}" + (f" {p['attrs']}" if p.get("attrs") else "")
    return f"#{r['id']:<5} [{r['kind']}] {head}\n        conf={r['confidence']} src={r['source']}\n        evidence: {r['evidence']}"


def stats(store: Store) -> dict:
    out: dict = {"pending": 0, "accepted": 0, "rejected": 0, "by_kind": {}}
    for r in store.staging_rows(None):
        out[r["status"]] = out.get(r["status"], 0) + 1
        k = out["by_kind"].setdefault(r["kind"], {"accepted": 0, "rejected": 0})
        if r["status"] in k:
            k[r["status"]] += 1
    scored = out["accepted"] + out["rejected"]
    out["scored"] = scored
    out["precision"] = out["accepted"] / scored if scored else None
    return out


def stats_text(s: dict) -> str:
    p = f"{s['precision']:.0%}" if s["precision"] is not None else "n/a"
    lines = [f"pending={s['pending']} accepted={s['accepted']} rejected={s['rejected']} precision={p} (bar {PRECISION_BAR:.0%}, min sample {MIN_SCORED})"]
    for k, v in s["by_kind"].items():
        tot = v["accepted"] + v["rejected"]
        lines.append(f"  {k}: {v['accepted']}/{tot} " + (f"({v['accepted']/tot:.0%})" if tot else ""))
    if s["precision"] is not None and s["precision"] < PRECISION_BAR:
        lines.append("  BELOW BAR: fix the extraction prompt or source-type handling, `kg staging reject --all`, re-run `kg extract`.")
    return "\n".join(lines)


def accept(store: Store, onto: Ontology, ids: list[int] | None, all_pending: bool = False, force: bool = False) -> dict:
    if all_pending:
        s = stats(store)
        if not force and (s["scored"] < MIN_SCORED or (s["precision"] or 0) < PRECISION_BAR):
            return {"error": f"refusing bulk accept: scored={s['scored']} precision={s['precision']}; "
                             f"score >= {MIN_SCORED} rows first (kg staging accept/reject <ids>) or pass --force"}
        rows = store.staging_rows("pending")
    else:
        rows = [r for r in store.staging_rows("pending") if r["id"] in set(ids or [])]
    res = ingest_staged(store, onto, rows)
    store.staging_set([r["id"] for r in rows], "accepted")
    store.commit()
    return res
