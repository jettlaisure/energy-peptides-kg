"""Pull paid orders from the site's D1 database into the inventory ledger (seeds/06_inventory_events.yaml).
Orders and customers stay in D1; only SKU, quantity, date and order id cross into the graph."""
from __future__ import annotations

import json
import re
import subprocess
import datetime as dt
from pathlib import Path

import yaml

from . import serve
from .store import ROOT, Store

EVENTS_SEED = ROOT / "seeds" / "06_inventory_events.yaml"
WEB = ROOT / "web"
DB_NAME = "energy-peptides-orders"


def _d1(sql: str, remote: bool) -> list[dict]:
    cmd = ["npx", "wrangler", "d1", "execute", DB_NAME, "--remote" if remote else "--local", "--json", "--command", sql]
    out = subprocess.run(cmd, cwd=WEB, capture_output=True, text=True, check=True).stdout
    data = json.loads(out[out.index("["):])
    return data[0]["results"]


def _next_event_number(doc: dict) -> int:
    nums = [int(m.group(1)) for it in doc["items"] if (m := re.match(r"IE-(\d+)", it["name"]))]
    return (max(nums) + 1) if nums else 1


def allocate(store: Store) -> dict[str, list[list]]:
    """Per SKU, its lots that still have stock, FEFO (lots without an expiry last), as [batch, remaining] pairs.
    Lots at zero are never chosen: a sale on an empty lot would drive stock negative (just-in-time SKUs sit on
    an emptied lot until the new kit is recorded)."""
    on_hand = {b["batch"]: b["on_hand"] for r in serve.stock(store) for b in r["batches"]}
    out: dict[str, list[list]] = {}
    for p in store.nodes("Product"):
        lots = [store.get(e["src"]) for e in store.edges(p["id"], "OF_PRODUCT", "in")]
        lots = [b for b in lots if on_hand.get(b["name"], 0) > 0]
        lots.sort(key=lambda b: str(b["attrs"].get("expires_on") or "9999"))
        out[p["attrs"].get("sku", "")] = [[b["name"], on_hand[b["name"]]] for b in lots]
    return out


def plan_events(rows: list[dict], lots: dict[str, list[list]], seen: set, start: int) -> tuple[list[dict], set, list[str], set]:
    """Turn paid order lines into `sold` events, splitting a line across lots when one lot cannot cover it.
    Returns (events, order ids fully recorded, skipped notes, order ids to mark synced without events).
    - paid, stock covers it  -> sold events; order marked synced
    - paid, not enough stock -> skipped and left unsynced, so the next pull retries once the lot is recorded
    - refunded before any pull -> no events (nothing was ever taken off the ledger); marked synced
    An order is marked synced only when every one of its lines was recorded."""
    events, skipped, blocked, refunded_only = [], [], set(), set()
    done_lines: dict[str, int] = {}
    n = start
    for row in rows:
        oid, sku, qty = row["id"], row["sku"], int(row["quantity"])
        ref = f"order {oid} {sku}"
        if row["status"] == "refunded":
            refunded_only.add(oid); continue
        if any(r == ref or r.startswith(ref + " ") for r in seen if r):
            done_lines[oid] = done_lines.get(oid, 0) + 1; continue
        avail = lots.get(sku, [])
        if sum(q for _, q in avail) < qty:
            skipped.append(f"{oid}: {sku} ×{qty} waits for a lot (on hand {sum(q for _, q in avail):g}); record the kit with /inventory")
            blocked.add(oid); continue
        need, parts = qty, []
        for lot in avail:
            if need == 0:
                break
            take = min(need, int(lot[1]))
            if take > 0:
                parts.append((lot[0], take)); lot[1] -= take; need -= take
        for i, (batch, take) in enumerate(parts):
            events.append({"name": f"IE-{n:04d}", "attrs": {"kind": "sold", "quantity": take, "occurred_on": row["created_at"][:10],
                           "reference": ref if i == 0 else f"{ref} lot {batch}"},
                           "edges": [{"rel": "AFFECTS", "to": f"Batch:{batch}"}]})
            n += 1
        done_lines[oid] = done_lines.get(oid, 0) + 1
    recorded = {oid for oid in done_lines if oid not in blocked}
    return events, recorded, skipped, refunded_only - recorded - blocked


def pull(store: Store, remote: bool = False, apply: bool = False, mark: bool = True) -> dict:
    rows = _d1("SELECT o.id, o.created_at, o.status, oi.sku, oi.quantity FROM orders o JOIN order_items oi ON oi.order_id=o.id "
               "WHERE o.status IN ('paid','refunded') AND o.ledger_synced_at IS NULL ORDER BY o.created_at", remote)
    doc = yaml.safe_load(EVENTS_SEED.read_text())
    seen = {it["attrs"].get("reference") for it in doc["items"]}
    events, recorded, skipped, refunded = plan_events(rows, allocate(store), seen, _next_event_number(doc))
    synced = recorded | refunded
    if apply and (events or synced):
        if events:
            doc["items"].extend(events)
            EVENTS_SEED.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=200))
        if synced and mark:
            ids = ",".join(f"'{i}'" for i in sorted(synced))
            _d1(f"UPDATE orders SET ledger_synced_at='{dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}' WHERE id IN ({ids})", remote)
    return {"orders": len(recorded), "events": len(events), "refunded_unpulled": len(refunded), "skipped": skipped,
            "applied": apply and bool(events or synced),
            "preview": [f"{i['name']} {i['attrs']['kind']} {i['attrs']['quantity']} × {i['attrs']['reference']} -> {i['edges'][0]['to']}" for i in events]}


def to_mark(rows: list[dict], seen: set) -> set:
    """Orders safe to mark synced: every line of a paid order already has its sale in the ledger seed, or the order
    was refunded before any of its lines reached the ledger. Derived from the committed ledger alone, so it is safe
    to run after a push and harmless to repeat."""
    lines: dict[str, list[dict]] = {}
    for r in rows:
        lines.setdefault(r["id"], []).append(r)
    def recorded(r):
        ref = f"order {r['id']} {r['sku']}"
        return any(s == ref or s.startswith(ref + " ") for s in seen if s)
    out = set()
    for oid, ls in lines.items():
        if all(r["status"] == "paid" for r in ls) and all(recorded(r) for r in ls):
            out.add(oid)
        elif all(r["status"] == "refunded" for r in ls) and not any(recorded(r) for r in ls):
            out.add(oid)
    return out


def mark(remote: bool = False) -> dict:
    """Mark orders synced in D1 once their sales are in the committed ledger (run after `git push`)."""
    rows = _d1("SELECT o.id, o.status, oi.sku FROM orders o JOIN order_items oi ON oi.order_id=o.id "
               "WHERE o.status IN ('paid','refunded') AND o.ledger_synced_at IS NULL", remote)
    seen = {it["attrs"].get("reference") for it in yaml.safe_load(EVENTS_SEED.read_text())["items"]}
    ids = to_mark(rows, seen)
    if ids:
        _d1(f"UPDATE orders SET ledger_synced_at='{dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}' "
            f"WHERE id IN ({','.join(repr(i) for i in sorted(ids))})", remote)
    return {"marked": len(ids)}
