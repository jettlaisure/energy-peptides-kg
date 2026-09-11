"""Graph -> site catalog JSON. The only data the website reads. Approved claims, approved FAQs,
verified studies only; internal attrs (cost) never included."""
from __future__ import annotations

import json
import re

import yaml

from . import serve
from .store import ROOT, Store, now

SITE_CFG = ROOT / "site.yaml"


def _node_public(n: dict, keys: tuple[str, ...]) -> dict:
    return {k: n["attrs"].get(k) for k in keys if n["attrs"].get(k) not in (None, "", [])}


def build(store: Store) -> dict:
    cfg = yaml.safe_load(SITE_CFG.read_text())
    stock = {r["product"]: r for r in serve.stock(store)}
    areas = {a["id"]: {"name": a["name"], "slug": a["attrs"].get("slug"), "summary": a["attrs"].get("summary"), "product_slugs": []}
             for a in store.nodes("ResearchArea")}
    faq_all = {f["id"]: {"id": f["name"], "question": f["attrs"]["question"], "answer": f["attrs"]["answer"],
                         "about": [store.get(e["dst"])["name"] for e in store.edges(f["id"], "ABOUT", "out")]}
               for f in store.nodes("FAQItem") if f["attrs"].get("status") == "approved"}
    pages = {}
    for pg in store.nodes("Page"):
        for e in store.edges(pg["id"], "FEATURES", "out"):
            pages[e["dst"]] = pg
    products = []
    for p in store.nodes("Product"):
        a = p["attrs"]
        if a.get("status") not in ("active", "coming_soon"):
            continue
        comps = []
        for e in store.edges(p["id"], "CONTAINS", "out"):
            c = store.get(e["dst"])
            comps.append({"name": c["name"], "type": c["type"], "aliases": c["aliases"], "confidence": c["confidence"],
                          "amount_mg": e["attrs"].get("amount_mg"),
                          **_node_public(c, ("summary", "class", "kind", "sequence", "molecular_formula", "molecular_weight", "cas_number"))})
        comps.sort(key=lambda c: (p["name"].find(c["name"]) if c["name"] in p["name"] else 10**6))
        comp_ids = {store.get(e["dst"])["id"] for e in store.edges(p["id"], "CONTAINS", "out")}
        claims, studies, faq_ids = [], [], set()
        for cid in comp_ids | {p["id"]}:
            for e in store.edges(cid, "ABOUT", "in"):
                s = store.get(e["src"])
                if s["type"] == "Claim" and s["attrs"].get("status") == "approved" and "product_page" in (s["attrs"].get("scope") or []):
                    supp = [store.get(x["dst"]) for x in store.edges(s["id"], "SUPPORTED_BY", "out")]
                    claims.append({"id": s["name"], "text": s["attrs"]["text"],
                                   "citations": [{"name": st["name"], "pmid": st["attrs"].get("pmid"), "year": st["attrs"].get("year"),
                                                  "journal": st["attrs"].get("journal"), "model": st["attrs"].get("model")}
                                                 for st in supp if st["attrs"].get("verified") is True]})
                if s["type"] == "FAQItem" and s["id"] in faq_all:
                    faq_ids.add(s["id"])
            for e in store.edges(cid, "INVESTIGATES", "in"):
                st = store.get(e["src"])
                if st["attrs"].get("verified") is True:
                    studies.append({"name": st["name"], **_node_public(st, ("pmid", "doi", "year", "journal", "model", "finding"))})
        page = pages.get(p["id"])
        if page:
            for e in store.edges(page["id"], "INCLUDES_FAQ", "out"):
                if e["dst"] in faq_all:
                    faq_ids.add(e["dst"])
        area = None
        for e in store.edges(p["id"], "BELONGS_TO", "out"):
            area = areas[e["dst"]]; area["product_slugs"].append(a.get("slug"))
        assets = [{"path": store.get(e["dst"])["name"], **_node_public(store.get(e["dst"]), ("asset_type", "alt_text", "url"))}
                  for e in store.edges(p["id"], "USES", "out")]
        coa = None
        batches = []
        for e in store.edges(p["id"], "OF_PRODUCT", "in"):
            b = store.get(e["src"])
            batches.append({"lot": b["name"], **_node_public(b, ("expires_on", "purity_measured", "coa_status"))})
            if b["attrs"].get("coa_status") == "published":
                for ce in store.edges(b["id"], "HAS_COA", "out"):
                    coa = {"lot": b["name"], "path": store.get(ce["dst"])["name"], "purity": b["attrs"].get("purity_measured")}
        related = sorted({store.get(e["src"])["attrs"].get("slug") for cid in comp_ids for e in store.edges(cid, "CONTAINS", "in")
                          if e["src"] != p["id"] and store.get(e["src"])["attrs"].get("status") == "active"} - {None})
        on_hand = stock.get(p["name"], {}).get("on_hand", 0)
        classes = [(c.get("class") or c.get("kind") or "").strip() for c in comps]
        comp_class = "Peptide blend" if len(comps) > 1 else (classes[0][:1].upper() + classes[0][1:] if classes and classes[0] else "Research compound")
        comp_slug = re.sub(r"[^a-z0-9]+", "-", comp_class.lower()).strip("-")
        products.append({
            "composition_class": comp_class, "composition_slug": comp_slug,
            "sku": a["sku"], "name": p["name"], "display_name": a.get("display_name"), "slug": a.get("slug"), "aliases": [x for x in p["aliases"] if len(x) > 4],
            "category": a.get("category"), "form": a.get("form"), "size_mg": a.get("size_mg"), "size_ml": a.get("size_ml"),
            "price_usd": a.get("price_usd"), "purity_spec": a.get("purity_spec"), "status": a.get("status"), "vial_ml": a.get("vial_ml"),
            "in_stock": on_hand > 0 and a.get("status") == "active", "on_hand": on_hand,
            "components": comps, "research_area": {"name": area["name"], "slug": area["slug"]} if area else None,
            "claims": claims, "studies": studies, "faqs": [faq_all[i] for i in sorted(faq_ids)],
            "assets": assets, "coa": coa, "batches": batches, "related_slugs": related,
            "page": {"title": page["attrs"].get("title"), "meta_description": page["attrs"].get("meta_description")} if page else None,
        })
    products.sort(key=lambda x: (x["category"] != "peptide", x["name"]))
    return {"generated_at": now(), "site": cfg, "products": products,
            "research_areas": sorted(areas.values(), key=lambda x: x["name"]),
            "faq": list(faq_all.values())}


def export(store: Store) -> str:
    return json.dumps(build(store), ensure_ascii=False, indent=2, default=str)
