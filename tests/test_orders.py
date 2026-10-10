"""Order pull: paid site orders become sold events without ever driving a lot negative."""
import pathlib

import pytest

from kg import orders
from kg.ingest import ingest
from kg.schema import Ontology
from kg.store import Store

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    st = Store(tmp_path_factory.mktemp("g") / "g.db")
    ingest(st, Ontology(ROOT / "ontology.yaml"))
    return st


def row(oid, sku, qty, status="paid"):
    return {"id": oid, "sku": sku, "quantity": qty, "status": status, "created_at": "2026-10-10T12:00:00Z"}


def test_empty_lots_are_never_allocated(store):
    lots = orders.allocate(store)
    assert lots["EP-KPV-10"] == []                         # FSD lot at zero: a JIT order waits for the new kit
    assert lots["EP-BPC-10"] == [["LOT-TBD-EP-BPC-10", 10]]


def test_jit_order_without_a_lot_waits_and_stays_unsynced(store):
    ev, recorded, skipped, refunded = orders.plan_events([row("A", "EP-KPV-10", 1)], orders.allocate(store), set(), 100)
    assert ev == [] and recorded == set() and refunded == set()
    assert "waits for a lot" in skipped[0]


def test_paid_order_is_sold_against_a_stocked_lot(store):
    ev, recorded, skipped, _ = orders.plan_events([row("B", "EP-BPC-10", 2)], orders.allocate(store), set(), 100)
    assert recorded == {"B"} and not skipped
    assert [(e["name"], e["attrs"]["quantity"], e["edges"][0]["to"]) for e in ev] == [("IE-0100", 2, "Batch:LOT-TBD-EP-BPC-10")]


def test_orders_in_one_pull_share_the_running_count(store):
    rows = [row("C", "EP-RT-20", 4), row("D", "EP-RT-20", 2)]          # 5 on hand
    ev, recorded, skipped, _ = orders.plan_events(rows, orders.allocate(store), set(), 1)
    assert recorded == {"C"} and len(ev) == 1 and "D: EP-RT-20" in skipped[0]


def test_line_splits_across_lots():
    lots = {"X": [["L1", 1], ["L2", 10]]}
    ev, recorded, _, _ = orders.plan_events([row("E", "X", 3)], lots, set(), 1)
    assert [(e["attrs"]["quantity"], e["edges"][0]["to"], e["attrs"]["reference"]) for e in ev] == [
        (1, "Batch:L1", "order E X"), (2, "Batch:L2", "order E X lot L2")]
    assert recorded == {"E"}


def test_refund_before_any_pull_writes_nothing():
    ev, recorded, skipped, refunded = orders.plan_events([row("F", "X", 1, "refunded")], {"X": [["L1", 5]]}, set(), 1)
    assert ev == [] and refunded == {"F"} and recorded == set()


def test_order_with_one_blocked_line_is_not_marked_synced():
    lots = {"X": [["L1", 5]], "Y": []}
    ev, recorded, skipped, _ = orders.plan_events([row("G", "X", 1), row("G", "Y", 1)], lots, set(), 1)
    assert recorded == set() and len(ev) == 1                          # X written; G retried, X deduped by reference
    ev2, recorded2, _, _ = orders.plan_events([row("G", "X", 1), row("G", "Y", 1)], {"X": [["L1", 4]], "Y": [["L9", 10]]},
                                              {"order G X"}, 2)
    assert recorded2 == {"G"} and [e["attrs"]["reference"] for e in ev2] == ["order G Y"]


def test_mark_only_orders_whose_sales_are_in_the_ledger():
    rows = [{"id": "P", "sku": "X", "status": "paid"}, {"id": "P", "sku": "Y", "status": "paid"},
            {"id": "Q", "sku": "X", "status": "paid"}, {"id": "R", "sku": "X", "status": "refunded"}]
    seen = {"order P X", "order P Y lot L2"}                  # P fully recorded (Y split across lots); Q not yet
    assert orders.to_mark(rows, seen) == {"P", "R"}           # R refunded before any sale was written
    assert orders.to_mark(rows, set()) == {"R"}               # nothing pushed: nothing paid is marked
