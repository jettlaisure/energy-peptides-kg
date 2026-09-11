"""Each competency question in competency_questions.md, executed against the seeded (real) graph."""
import pathlib
import pytest

from kg import fuse, serve
from kg.ingest import ingest
from kg.schema import Ontology, validate_graph
from kg.store import Store

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    db = tmp_path_factory.mktemp("kg") / "graph.db"
    st, onto = Store(db), Ontology(ROOT / "ontology.yaml")
    r = ingest(st, onto, ROOT / "seeds")
    assert not r["errors"], r["errors"]
    return st, onto


def test_stage7_graph_conforms_to_ontology(graph):
    st, onto = graph
    assert validate_graph(st, onto) == []


def test_q1_products_containing_peptide_and_stock(graph):
    st, _ = graph
    rows = {r["product"]: r for r in serve.stock(st)}
    assert rows["BPC-157 10mg"]["on_hand"] == 10 and rows["Retatrutide 20mg"]["on_hand"] == 5
    assert rows["BPC-157 10mg"]["batches"][0]["batch"] == "LOT-TBD-EP-BPC-10"
    assert sum(r["on_hand"] for r in rows.values()) == 58   # sheet total


def test_q2_expiring_batches_none_known_yet(graph):
    st, _ = graph
    assert "## Batches expiring within 90 days (0)" in serve.gaps(st)


def test_q3_q14_product_page_context_is_minimal_and_complete(graph):
    st, onto = graph
    ctx = serve.context(st, onto, "product_page", "Product:BPC-157 10mg")
    assert "Claim: CL-1" in ctx and "Claim: CL-2" in ctx and "Claim: CL-3" in ctx   # prohibited kept for verifiers
    assert "Chang 2011" in ctx and "verified=True" in ctx
    assert "CR-RUO" in ctx and "BR-PRODUCT-PAGE-STRUCTURE" in ctx
    assert "InventoryEvent" not in ctx and "cost_usd" not in ctx and "5.5" not in ctx   # ledger detail + margins excluded
    assert "Stock summary" in ctx and "on_hand=10" in ctx
    assert "BPC-157 / TB-500 20mg" in ctx                    # sibling blend for cross-linking


def test_internal_attrs_only_in_inventory_recipe(graph):
    st, onto = graph
    assert "cost_usd=5.5" in serve.context(st, onto, "inventory", "Product:BPC-157 10mg")
    assert "cost_usd" not in serve.context(st, onto, "marketing", "Product:BPC-157 10mg")


def test_compound_products_flow_through_recipes(graph):
    st, onto = graph
    ctx = serve.context(st, onto, "product_page", "Product:NAD+ 500mg")
    assert "Compound: NAD+" in ctx and "Claim: CL-9" in ctx and "Covarrubias 2021" in ctx
    ctx = serve.context(st, onto, "product_page", "Product:Bacteriostatic water 10ml")
    assert "Compound: Bacteriostatic water" in ctx and "Claim: CL-11" in ctx


def test_q4_q5_rules_by_scope(graph):
    st, _ = graph
    assert {n["name"] for n in serve.query(st, "BrandRule", {"scope": "product_page"})} >= {"BR-TONE", "BR-PRODUCT-PAGE-STRUCTURE"}
    assert "CR-NO-BRAND-COMPARISON" in {n["name"] for n in serve.query(st, "ComplianceRule", {"scope": "ads"})}


def test_q6_q8_q11_gaps(graph):
    st, _ = graph
    g = serve.gaps(st)
    assert "- nad+ research" in g                                # keyword nobody targets
    assert "## Studies NOT yet verified (cannot be cited) (0)" in g and "Chang 2011" in g
    assert "## Active products with no live product page (7)" in g   # 14 coming_soon SKUs are not counted
    assert "## Live pages possibly stale (0)" in g


def test_q7_faq_context(graph):
    st, onto = graph
    ctx = serve.context(st, onto, "faq_seo", "Peptide:BPC-157")
    assert "FAQItem: FAQ-1" in ctx and "Page: /faq" in ctx and "Keyword: what is bpc-157" in ctx


def test_q9_path_batch_to_research_area(graph):
    st, _ = graph
    p = serve.path(st, "Batch:LOT-TBD-EP-BPC-10", "ResearchArea:Tissue repair and recovery")
    assert "OF_PRODUCT" in p and "BELONGS_TO" in p


def test_q15_blends_via_card(graph):
    st, _ = graph
    c = serve.card(st, "Peptide:BPC-157")
    assert "Product: BPC-157 / TB-500 20mg" in c and "Product: BPC-157 10mg" in c


def test_q16_prohibited_claims(graph):
    st, _ = graph
    assert {n["name"] for n in serve.query(st, "Claim", {"status": "prohibited"})} == {"CL-3", "CL-5", "CL-8", "CL-10", "CL-20"}


def test_alias_resolution_dictionary_first(graph):
    st, _ = graph
    assert st.resolve("Peptide", "Body Protection Compound-157")["name"] == "BPC-157"
    assert st.resolve("Product", "Wolverine")["name"] == "BPC-157 / TB-500 20mg"
    assert st.resolve("Product", "bb20")["attrs"]["sku"] == "EP-B1-20"       # sheet's original code still resolves
    assert st.resolve("Product", "KLOW")["attrs"]["sku"] == "EP-B2-80"       # nickname resolves internally, never shown
    assert st.resolve("Compound", "bac water")["name"] == "Bacteriostatic water"


def test_stage5_domain_range_rejects_hallucinated_structure(graph):
    _, onto = graph
    assert onto.check_edge("CONTAINS", "Peptide", "Product") is not None
    assert onto.check_edge("SUPPLIED_BY", "Product", "Supplier") is not None
    assert onto.check_edge("CONTAINS", "Product", "Compound") is None


def test_stage8_fusion_merges_alias_duplicate(tmp_path):
    st, onto = Store(tmp_path / "g.db"), Ontology(ROOT / "ontology.yaml")
    assert not ingest(st, onto, ROOT / "seeds")["errors"]
    dup = st.upsert_node("Peptide", "Pentadecapeptide BPC-157 compound", {"class": "gastric pentadecapeptide"}, source="doc-x")
    st.add_edge(dup["id"], "RESEARCHED_FOR", "ResearchArea:tissuerepairandrecovery", source="doc-x")
    st.commit()
    r = fuse.run(st, onto, apply=False)
    assert ("Peptide:bpc157", dup["id"]) in {(k, d) for k, d, _, _ in r["auto"]}
    fuse.run(st, onto, apply=True)
    assert st.get(dup["id"]) is None
    keep = st.get("Peptide:bpc157")
    assert "Pentadecapeptide BPC-157 compound" in keep["aliases"] and keep["merged_from"]


def test_conflicting_attribute_is_recorded_not_overwritten(tmp_path):
    st, onto = Store(tmp_path / "g.db"), Ontology(ROOT / "ontology.yaml")
    ingest(st, onto, ROOT / "seeds")
    st.upsert_node("Peptide", "BPC-157", {"molecular_weight": 1419.6}, source="supplier-coa-2026")
    n = st.get("Peptide:bpc157")
    assert n["attrs"]["molecular_weight"] == 1419.5 and "molecular_weight" in n["conflicts"]


def test_catalog_has_21_skus_with_one_pattern(graph):
    st, _ = graph
    prods = [p for p in st.nodes("Product") if p["attrs"]["status"] in ("active", "coming_soon")]
    skus = [p["attrs"]["sku"] for p in prods]
    assert len(skus) == 21 and len(set(skus)) == 21
    drafts = {p["name"] for p in st.nodes("Product") if p["attrs"]["status"] == "draft"}
    assert drafts == {"Retatrutide 15mg", "GLOW 70mg"}                      # labelled, not yet priced, off the site
    import re
    assert all(re.fullmatch(r"EP-[A-Z0-9]{2,4}-\d+", s) for s in skus)
    assert sum(p["attrs"]["status"] == "active" for p in prods) == 7
    assert not any(p["attrs"].get("vials_per_unit") for p in prods)          # sold by the vial, no kits
    assert st.resolve("Product", "KLOW")["attrs"]["display_name"] == "KLOW"
