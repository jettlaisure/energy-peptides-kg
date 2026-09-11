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


def pull(store: Store, remote: bool = False, apply: bool = False) -> dict:
    orders = _d1("SELECT o.id, o.created_at, o.status, oi.sku, oi.quantity FROM orders o JOIN order_items oi ON oi.order_id=o.id "
                 "WHERE o.status IN ('paid','refunded') AND o.ledger_synced_at IS NULL ORDER BY o.created_at", remote)
    doc = yaml.safe_load(EVENTS_SEED.read_text())
    seen = {it["attrs"].get("reference") for it in doc["items"]}
    n = _next_event_number(doc)
    sku_to_batch: dict[str, str] = {}
    on_hand = {b["batch"]: b["on_hand"] for r in serve.stock(store) for b in r["batches"]}
    for p in store.nodes("Product"):
        batches = [store.get(e["src"]) for e in store.edges(p["id"], "OF_PRODUCT", "in")]
        if batches:   # FEFO among lots with stock; lots without an expiry sort last
            ordered = sorted(batches, key=lambda b: (on_hand.get(b["name"], 0) <= 0, str(b["attrs"].get("expires_on") or "9999")))
            sku_to_batch[p["attrs"]["sku"]] = ordered[0]["name"]
    new_items, touched, skipped = [], set(), []
    for row in orders:
        ref = f"order {row['id']} {row['sku']}"
        if ref in seen:
            continue
        batch = sku_to_batch.get(row["sku"])
        if not batch:
            skipped.append(f"{row['id']}: no batch for {row['sku']}"); continue
        kind = "sold" if row["status"] == "paid" else "released"
        new_items.append({"name": f"IE-{n:04d}", "attrs": {"kind": kind, "quantity": int(row["quantity"]),
                          "occurred_on": row["created_at"][:10], "reference": ref},
                          "edges": [{"rel": "AFFECTS", "to": f"Batch:{batch}"}]})
        n += 1; touched.add(row["id"])
    if apply and new_items:
        doc["items"].extend(new_items)
        EVENTS_SEED.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=200))
        ids = ",".join(f"'{i}'" for i in touched)
        _d1(f"UPDATE orders SET ledger_synced_at='{dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}' WHERE id IN ({ids})", remote)
    return {"orders": len(touched), "events": len(new_items), "skipped": skipped, "applied": apply and bool(new_items),
            "preview": [f"{i['name']} {i['attrs']['kind']} {i['attrs']['quantity']} × {i['attrs']['reference']} -> {i['edges'][0]['to']}" for i in new_items]}
