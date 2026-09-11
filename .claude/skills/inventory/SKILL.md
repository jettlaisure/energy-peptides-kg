---
name: inventory
description: Record Energy Peptides stock movements and new batches in the knowledge graph ledger (receive, sell, reserve, release, adjust, damaged, expire, new batch) and report stock position, expiries and low stock.
---
# Inventory — executes taskgraphs/inventory.yaml (sequential; one agent, no fan-out)

1. Read the position first: `uv run kg stock "<Product name>" --events` (or `uv run kg stock` for all).
2. Draft the seed entry:
   - New lot → `seeds/05_batches.yaml`: name = lot number; attrs manufactured_on, expires_on, purity_measured, coa_status, unit; edges OF_PRODUCT, SUPPLIED_BY, HAS_COA (add the COA to `seeds/04_assets.yaml` first).
   - Movement → `seeds/06_inventory_events.yaml`: next `IE-nnnn`; attrs kind, quantity (positive; `adjusted` is signed), occurred_on, reference; edge AFFECTS the batch.
   - The ledger is append-only. Never edit or delete a past event; correct with an `adjusted` event whose reference explains why.
3. Human gate only for write-downs (`adjusted` negative, `damaged`, `expired`): show the proposed event and the resulting on-hand, wait for approval. Receive/sell/reserve/release are reversible by a counter-event and need no gate.
4. `uv run kg ingest && uv run kg validate && uv run kg stock "<Product name>"`.
   Then keep Kashu's catalog in step (a product going in or out of stock flips its active flag there):
   `uv run kg sync plan --adapter kashu` to preview, `uv run kg sync apply --adapter kashu --yes` to push. Same after any price change.
5. `uv run kg gaps --expiry-days 90 --low-stock 3` and report expiries and low stock.
