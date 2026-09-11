"""kg — command-line surface for the Energy Peptides knowledge graph."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import fuse as fuse_mod
from . import gate, serve
from .ingest import SEEDS_DIR, ingest
from .schema import ONTOLOGY_PATH, Ontology, validate_graph
from .store import DB_PATH, Store


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kg", description="Energy Peptides knowledge graph")
    ap.add_argument("--db", default=str(DB_PATH))
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("rebuild", help="delete the DB and re-ingest all seeds (derived data; safe)")
    p = sub.add_parser("ingest", help="ingest seeds/*.yaml (structured → graph, no NLP)")
    p.add_argument("--seeds", default=str(SEEDS_DIR)); p.add_argument("--lenient", action="store_true")
    sub.add_parser("validate", help="stage-7 check of the stored graph against the ontology")
    p = sub.add_parser("index", help="layer 0/1: tiny listing of what exists"); p.add_argument("--max-names", type=int, default=40)
    p = sub.add_parser("card", help="layer 2: one entity + 1 hop"); p.add_argument("ref")
    p = sub.add_parser("context", help="layer 3: task recipe subgraph (GraphRAG)")
    p.add_argument("recipe"); p.add_argument("ref"); p.add_argument("--max-lines", type=int, default=300)
    sub.add_parser("recipes", help="list context recipes")
    p = sub.add_parser("path", help="shortest path between two entities"); p.add_argument("a"); p.add_argument("b"); p.add_argument("--max-hops", type=int, default=4)
    p = sub.add_parser("query", help="filter nodes: kg query Claim --status approved --scope ads")
    p.add_argument("type"); p.add_argument("filters", nargs=argparse.REMAINDER)
    p = sub.add_parser("stock", help="on-hand per product/batch from InventoryEvents"); p.add_argument("product", nargs="?"); p.add_argument("--events", action="store_true")
    p = sub.add_parser("gaps", help="maintenance report: expiries, low stock, missing pages/keywords/citations, stale pages")
    p.add_argument("--expiry-days", type=int, default=90); p.add_argument("--low-stock", type=int, default=3)
    p = sub.add_parser("export"); p.add_argument("--format", choices=["json", "triples", "mermaid", "site"], default="json"); p.add_argument("--out")
    p = sub.add_parser("extract", help="LLM extraction of a text/markdown file into staging (stages 4-6)"); p.add_argument("file")
    p = sub.add_parser("staging", help="stage 7 gate over extracted facts")
    p.add_argument("action", choices=["list", "stats", "accept", "reject", "candidates"])
    p.add_argument("ids", nargs="*", type=int); p.add_argument("--all", action="store_true"); p.add_argument("--force", action="store_true")
    p.add_argument("--sample", type=int, default=50)
    p = sub.add_parser("fuse", help="stage 8: find/merge duplicates")
    p.add_argument("action", nargs="?", default="run", choices=["run", "review", "merge", "reject"])
    p.add_argument("a", nargs="?"); p.add_argument("b", nargs="?"); p.add_argument("--apply", action="store_true")
    p = sub.add_parser("map", help="write the visual map for humans (data/graph-map.html); not for AI context")
    p.add_argument("--out")
    p = sub.add_parser("sync", help="push the catalog to a commerce/payment platform (graph is source of truth)")
    p.add_argument("action", choices=["plan", "apply", "export"])
    p.add_argument("--adapter", default="file"); p.add_argument("--store", help="kashu: target store id (default TAGADA_CATALOG_STORE_ID)"); p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.add_argument("--out", help="export: write CSV here instead of stdout")
    p = sub.add_parser("orders", help="pull paid site orders (Cloudflare D1) into the inventory ledger")
    p.add_argument("action", choices=["pull"]); p.add_argument("--remote", action="store_true", help="production D1 instead of local")
    p.add_argument("--apply", action="store_true", help="write events to seeds and mark orders synced (default: preview)")
    p = sub.add_parser("add-edge", help="manual edge: kg add-edge 'Page:/faq' INCLUDES_FAQ 'FAQItem:FAQ-1'")
    p.add_argument("src"); p.add_argument("rel"); p.add_argument("dst"); p.add_argument("--source", default="manual"); p.add_argument("--confidence", default="high")

    a = ap.parse_args(argv)
    onto = Ontology(ONTOLOGY_PATH)
    db = Path(a.db)
    if a.cmd == "rebuild":
        if db.exists():
            db.unlink()
        st = Store(db)
        r = ingest(st, onto)
        _report_ingest(r)
        _refresh_map(st, onto, r)
        print(serve.index(st))
        return 0 if not r["errors"] else 1
    st = Store(db)

    if a.cmd == "ingest":
        r = ingest(st, onto, Path(a.seeds), strict=not a.lenient)
        _report_ingest(r)
        _refresh_map(st, onto, r)
        return 0 if not r["errors"] else 1
    if a.cmd == "validate":
        issues = validate_graph(st, onto)
        print("\n".join(issues) if issues else "OK: graph conforms to ontology")
        return 1 if issues else 0
    if a.cmd == "index":
        print(serve.index(st, a.max_names))
    elif a.cmd == "card":
        print(serve.card(st, a.ref))
    elif a.cmd == "context":
        print(serve.context(st, onto, a.recipe, a.ref, a.max_lines))
    elif a.cmd == "recipes":
        for k, v in onto.recipes.items():
            print(f"- {k}: {v['desc']} (seed: {', '.join(v['seed_types'])})")
    elif a.cmd == "path":
        print(serve.path(st, a.a, a.b, a.max_hops))
    elif a.cmd == "query":
        where = {}
        it = iter(a.filters)
        for tok in it:
            if tok.startswith("--"):
                where[tok[2:]] = next(it, "")
        for n in serve.query(st, a.type, where):
            print(f"- {n['name']}: {serve._attrs_line(n['attrs'])}  [conf: {n['confidence']}]")
    elif a.cmd == "stock":
        print(serve.stock_text(serve.stock(st, a.product, a.events), a.events))
    elif a.cmd == "gaps":
        print(serve.gaps(st, a.expiry_days, a.low_stock))
    elif a.cmd == "export":
        if a.format == "site":
            from .site_export import export as site_export
            text = site_export(st)
        else:
            text = serve.export(st, a.format)
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(text); print(f"wrote {a.out}")
        else:
            print(text)
    elif a.cmd == "extract":
        from .extract import extract_file
        print(json.dumps(extract_file(st, onto, Path(a.file)), indent=2))
        print("Staged. Next: `kg staging list`, score a sample, then `kg staging accept ...`.")
    elif a.cmd == "staging":
        if a.action == "list":
            for r in gate.sample(st, a.sample):
                print(gate.fmt_row(r))
        elif a.action == "stats":
            print(gate.stats_text(gate.stats(st)))
        elif a.action == "accept":
            r = gate.accept(st, onto, a.ids, a.all, a.force)
            print(json.dumps(r, indent=2)); return 1 if r.get("error") else 0
        elif a.action == "reject":
            ids = [r["id"] for r in st.staging_rows("pending")] if a.all else a.ids
            st.staging_set(ids, "rejected"); st.commit(); print(f"rejected {len(ids)}")
        elif a.action == "candidates":
            for c in st.candidates():
                print(f"- [{c['kind']}] {c['text']}  ({c['source']})")
    elif a.cmd == "fuse":
        if a.action == "run":
            r = fuse_mod.run(st, onto, apply=a.apply)
            for keep, drop, s, why in r["auto"]:
                print(f"{'MERGED' if a.apply else 'would merge'} {drop} -> {keep} ({s:.2f}: {', '.join(why)})")
            for x, y, s, why in r["review"]:
                print(f"REVIEW {x} ~ {y} ({s:.2f}: {', '.join(why)})")
            print(f"auto={len(r['auto'])} review={len(r['review'])} rejected={r['rejected']}" + ("" if a.apply else "  (dry run; add --apply)"))
        elif a.action == "review":
            for r in st.review_rows():
                print(f"- {r['a']} ~ {r['b']} ({r['score']:.2f}: {', '.join(r['reasons'])})  → kg fuse merge A B | kg fuse reject A B")
        elif a.action == "merge":
            fuse_mod.merge(st, a.a, a.b); st.review_set(a.a, a.b, "merged"); st.commit(); print(f"merged {a.b} into {a.a}")
        elif a.action == "reject":
            st.review_set(a.a, a.b, "rejected"); st.commit(); print("marked distinct")
    elif a.cmd == "map":
        from .map import render, MAP_PATH
        print(f"wrote {render(st, onto, Path(a.out) if a.out else MAP_PATH)}")
    elif a.cmd == "sync":
        from . import sync
        local = sync.snapshot(st)
        if a.action == "export":
            text = sync.export_csv(local)
            if a.out:
                Path(a.out).write_text(text); print(f"wrote {a.out} ({len(local)} rows)")
            else:
                print(text, end="")
            return 0
        adapter = sync.get_adapter(a.adapter, a.store)
        plan = sync.plan_for(adapter, local)
        print(sync.plan_text(plan, adapter.name))
        if a.action == "plan" or plan.empty():
            return 0
        if not a.yes:
            ans = input(f"Apply {len(plan.create)} creates and {len(plan.update)} updates to '{adapter.name}'? [y/N] ")
            if ans.strip().lower() not in ("y", "yes"):
                print("aborted; nothing written"); return 1
        ids = adapter.apply(plan)
        n = sync.write_back_ids(ids, adapter.name, st)
        from .ingest import ingest as _ingest
        r = _ingest(st, onto)
        print(f"applied; {len(ids)} platform ids recorded in seeds/14_platform_ids.yaml ({n} total); re-ingest errors={len(r['errors'])}")
        return 0 if not r["errors"] else 1
    elif a.cmd == "orders":
        from .orders import pull
        r = pull(st, remote=a.remote, apply=a.apply)
        for line in r["preview"]:
            print(line)
        for sk in r["skipped"]:
            print("skipped:", sk)
        print(f"orders={r['orders']} events={r['events']} applied={r['applied']}" + ("" if a.apply else "  (preview; add --apply, then `kg ingest`)"))
    elif a.cmd == "add-edge":
        s, d = st.resolve_any(a.src), st.resolve_any(a.dst)
        if not s or not d:
            print("endpoint not found"); return 1
        err = onto.check_edge(a.rel, s["type"], d["type"])
        if err:
            print(err); return 1
        st.add_edge(s["id"], a.rel, d["id"], {}, a.source, a.confidence); st.commit(); print("ok")
    return 0


def _refresh_map(st, onto, r: dict) -> None:
    """Keep data/graph-map.html current after every successful ingest. Never fails the ingest."""
    if r.get("errors"):
        return
    try:
        from .map import render
        render(st, onto)
    except Exception as e:  # the map is a convenience; the graph is what matters
        print(f"  (map not refreshed: {e})")


def _report_ingest(r: dict):
    print(f"ingested nodes={r['nodes']} edges={r['edges']} warnings={len(r['warnings'])} errors={len(r['errors'])}")
    for w in r["warnings"]:
        print("  warn:", w)
    for e in r["errors"]:
        print("  ERROR:", e)
    if r["errors"]:
        print("  (strict mode: transaction rolled back; fix seeds and re-run)")


if __name__ == "__main__":
    sys.exit(main())
