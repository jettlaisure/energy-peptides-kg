import pathlib, shutil
from kg import sync
from kg.ingest import ingest
from kg.schema import Ontology, validate_graph
from kg.store import Store

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _graph(tmp_path):
    """Graph from the real seeds minus platform ids, so adapter tests start from an unsynced catalog."""
    seeds = tmp_path / "seeds_base"
    shutil.copytree(ROOT / "seeds", seeds, ignore=shutil.ignore_patterns("_archive", "14_platform_ids.yaml"))
    st, onto = Store(tmp_path / "g.db"), Ontology(ROOT / "ontology.yaml")
    assert not ingest(st, onto, seeds)["errors"]
    return st, onto


def test_snapshot_matches_sheet_and_hides_cost(tmp_path):
    st, _ = _graph(tmp_path)
    items = {i.sku: i for i in sync.snapshot(st)}
    assert len(items) == 21 and {"EP-RT-20", "EP-BPC-10", "EP-B1-20", "EP-CU-50", "EP-CU-100", "EP-NAD-500", "EP-BAC-10", "EP-TESA-20"} <= set(items)
    assert items["EP-BPC-10"].quantity == 10 and items["EP-BPC-10"].price_usd == 59 and items["EP-BPC-10"].variant == "10mg"
    assert items["EP-B1-20"].family == "BPC-157 / TB-500" and items["EP-B1-20"].variant == "20mg"
    assert items["EP-TESA-20"].status == "coming_soon" and items["EP-TESA-20"].quantity == 0
    assert "EP-RT-15" not in items and "EP-B3-70" not in items             # drafts never sync
    assert items["EP-BAC-10"].family == "Bacteriostatic water" and items["EP-BAC-10"].variant == "10ml" and "10 ml per vial" in items["EP-BAC-10"].description
    assert sync.RUO_LINE in items["EP-RT-20"].description
    csv = sync.export_csv(sync.snapshot(st))
    assert "cost" not in csv and "13.5" not in csv and "185.5" not in csv        # margins never leave the graph


def test_plan_apply_is_idempotent_and_writes_back_ids(tmp_path):
    st, onto = _graph(tmp_path)
    adapter = sync.FileAdapter(tmp_path / "remote.json")
    local = sync.snapshot(st)
    plan = sync.diff(local, adapter.fetch())
    assert len(plan.create) == 21 and not plan.update
    ids = adapter.apply(plan)
    seed = tmp_path / "14.yaml"
    assert sync.write_back_ids(ids, "file", st, seed) == 21
    seeds = tmp_path / "seeds"; shutil.copytree(ROOT / "seeds", seeds, ignore=shutil.ignore_patterns("_archive", "14_platform_ids.yaml")); shutil.copy(seed, seeds / "14_platform_ids.yaml")
    assert not ingest(st, onto, seeds)["errors"] and validate_graph(st, onto) == []
    assert st.resolve("Product", "BPC-157 10mg")["attrs"]["external_id"] == "file_ep-bpc-10"
    assert sync.diff(sync.snapshot(st), adapter.fetch()).empty()
    src = st.resolve("Product", "BPC-157 10mg")["source"]   # same source may overwrite; a different one only records a conflict
    st.upsert_node("Product", "BPC-157 10mg", {"price_usd": 64.00}, source=src); st.commit()
    plan = sync.diff(sync.snapshot(st), adapter.fetch())
    assert len(plan.update) == 1 and "price_usd" in plan.update[0][2]


class _FakeKashu:
    """In-memory stand-in with the same projection/compare rules as KashuAdapter."""
    name, compare = "kashu", sync.KashuAdapter.compare
    def __init__(self): self.remote = {}
    project = sync.KashuAdapter.project
    title = staticmethod(sync.KashuAdapter.title)
    def fetch(self): return list(self.remote.values())
    def apply(self, plan):
        for it in plan.create: self.remote[it.sku] = sync.dataclasses.replace(it, external_id="p_" + it.sku)
        for l, r, ch in plan.update: self.remote[l.sku] = sync.dataclasses.replace(l, external_id=r.external_id if "price_usd" not in ch else "p2_" + l.sku)
        return {k: v.external_id for k, v in self.remote.items()}


def test_kashu_projection_and_resync(tmp_path):
    st, _ = _graph(tmp_path)
    fake = _FakeKashu()
    local = sync.snapshot(st)
    plan = sync.plan_for(fake, local)
    assert len(plan.create) == 21
    fake.apply(plan)
    by = fake.remote
    assert by["EP-RT-20"].status == "active" and by["EP-RT-10"].status == "inactive"      # stocked vs coming soon
    assert by["EP-B2-80"].name.startswith("KLOW 80mg (") and "GHK-Cu 50 mg" in by["EP-B2-80"].description
    assert "cost" not in by["EP-RT-20"].description and sync.RUO_LINE in by["EP-RT-20"].description
    assert sync.plan_for(fake, sync.snapshot(st)).empty()                                   # idempotent
