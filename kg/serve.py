"""Stage 9: serve the graph to agents with progressive disclosure.
Layers: index (tiny) -> card (one node, 1 hop) -> context (task recipe subgraph) -> path/query."""
from __future__ import annotations

import datetime as dt
import json
from collections import deque

from .schema import Ontology
from .store import Store, now

EVENT_SIGN = {"received": 1, "sold": -1, "reserved": -1, "released": 1, "adjusted": 1, "damaged": -1, "expired": -1}


def _prov(x: dict) -> str:
    return f"[src: {x['source']}; conf: {x['confidence']}]"


def _attrs_line(attrs: dict, skip=()) -> str:
    parts = []
    for k, v in attrs.items():
        if k in skip or v in (None, "", [], {}):
            continue
        if isinstance(v, list):
            v = "; ".join(map(str, v))
        parts.append(f"{k}={v}")
    return "  ".join(parts)


# ---- layer 1: index -------------------------------------------------------
def index(store: Store, max_names: int = 40) -> str:
    c = store.counts()
    lines = [f"# Energy Peptides KG index — {sum(c['nodes'].values())} nodes, {c['edges']} edges ({now()})"]
    for t, n in sorted(c["nodes"].items()):
        names = [x["name"] for x in store.nodes(t)]
        shown = ", ".join(names[:max_names]) + (f", … +{len(names)-max_names}" if len(names) > max_names else "")
        lines.append(f"- {t} ({n}): {shown}")
    lines.append("Next: `kg card <Type:Name>` for one entity, `kg context <recipe> <Type:Name>` for a task bundle.")
    return "\n".join(lines)


# ---- layer 2: card ---------------------------------------------------------
def card(store: Store, ref: str) -> str:
    n = store.resolve_any(ref)
    if not n:
        return f"not found: {ref}"
    lines = [f"## {n['type']}: {n['name']}  {_prov(n)}"]
    if n["aliases"]:
        lines.append(f"aliases: {', '.join(n['aliases'])}")
    if n["attrs"]:
        lines.append(_attrs_line(n["attrs"]))
    if n["conflicts"]:
        lines.append("CONFLICTS (unresolved, per-source): " + json.dumps(n["conflicts"], ensure_ascii=False))
    if n["valid_to"]:
        lines.append(f"valid_to: {n['valid_to']} (STALE — superseded)")
    for e in store.edges(n["id"], direction="out"):
        d = store.get(e["dst"])
        lines.append(f"- {e['rel']} -> {d['type']}: {d['name']}" + (f" {e['attrs']}" if e["attrs"] else "") + f"  {_prov(e)}")
    for e in store.edges(n["id"], direction="in"):
        s = store.get(e["src"])
        lines.append(f"- <- {e['rel']} <- {s['type']}: {s['name']}" + (f" {e['attrs']}" if e["attrs"] else "") + f"  {_prov(e)}")
    return "\n".join(lines)


# ---- stock summary (events -> on-hand) -------------------------------------
def stock(store: Store, product_ref: str | None = None, with_events: bool = False) -> list[dict]:
    products = [store.resolve_any(product_ref)] if product_ref else store.nodes("Product")
    out = []
    for p in products:
        if not p:
            continue
        batches = []
        for e in store.edges(p["id"], "OF_PRODUCT", "in"):
            b = store.get(e["src"])
            events = []
            on_hand = 0
            for ee in store.edges(b["id"], "AFFECTS", "in"):
                ev = store.get(ee["src"])
                q = float(ev["attrs"].get("quantity", 0))
                delta = q * EVENT_SIGN.get(ev["attrs"].get("kind", ""), 0)
                on_hand += delta
                events.append({"id": ev["name"], **ev["attrs"], "delta": delta})
            events.sort(key=lambda x: str(x.get("occurred_on", "")))
            batches.append({"batch": b["name"], "on_hand": on_hand, "expires_on": b["attrs"].get("expires_on"),
                            "purity": b["attrs"].get("purity_measured"), "coa_status": b["attrs"].get("coa_status"),
                            "events": events if with_events else None})
        out.append({"product": p["name"], "sku": p["attrs"].get("sku"), "status": p["attrs"].get("status"),
                    "on_hand": sum(b["on_hand"] for b in batches), "batches": batches})
    return out


def stock_text(rows: list[dict], with_events: bool = False) -> str:
    lines = []
    for r in rows:
        lines.append(f"- {r['product']} (sku {r['sku']}, {r['status']}): on_hand={r['on_hand']:g}")
        for b in r["batches"]:
            lines.append(f"    batch {b['batch']}: on_hand={b['on_hand']:g} expires={b['expires_on']} purity={b['purity']} coa={b['coa_status']}")
            if with_events and b["events"]:
                for ev in b["events"]:
                    lines.append(f"      {ev.get('occurred_on')} {ev.get('kind')} {ev.get('quantity')} ({ev.get('reference','')}) Δ{ev['delta']:+g}")
    return "\n".join(lines) or "(no products)"


# ---- layer 3: task context via recipe (GraphRAG) ---------------------------
def _as_list(v) -> list:
    return v if isinstance(v, list) else [v]


def _scope_match(node: dict, scope: str) -> bool:
    s = node["attrs"].get("scope") or []
    return scope in s or "all" in s


def context(store: Store, onto: Ontology, recipe_name: str, seed_ref: str, max_lines: int = 300) -> str:
    recipe = onto.recipes.get(recipe_name)
    if recipe is None:
        return f"unknown recipe {recipe_name!r}; available: {', '.join(onto.recipes)}"
    seed = store.resolve_any(seed_ref)
    if seed is None:
        return f"not found: {seed_ref}. Run `kg index` to see what exists, or add it to seeds/ and `kg ingest`."
    if seed["type"] not in recipe["seed_types"]:
        return f"recipe {recipe_name} expects a seed of type {recipe['seed_types']}, got {seed['type']}"

    collected: dict[str, dict] = {seed["id"]: seed}
    edges: dict[tuple, dict] = {}
    for step in recipe.get("expand", []):
        frontier = [n for n in list(collected.values()) if not step.get("from") or n["type"] in _as_list(step["from"])]
        for n in frontier:
            for e in store.edges(n["id"], step["rel"], step["dir"]):
                other_id = e["dst"] if step["dir"] == "out" else e["src"]
                other = store.get(other_id)
                if other is None or (step.get("type") and other["type"] not in _as_list(step["type"])):
                    continue
                if other.get("valid_to"):
                    continue  # superseded facts stay in the graph but not in task context
                collected[other_id] = other
                edges[(e["src"], e["rel"], e["dst"])] = e
    globals_ = []
    for g in recipe.get("global", []):
        for n in store.nodes(g["type"]):
            if _scope_match(n, g["scope"]):
                globals_.append(n)

    # internal attrs (e.g. cost) stay out of copy-writing contexts
    internal = {t: {k for k, spec in onto.attr_spec(t).items() if (spec or {}).get("internal")} for t in onto.types()}
    if recipe.get("include_internal"):
        internal = {}
    # serialise: grouped by head entity, compact triples with provenance
    lines = [f"# CONTEXT recipe={recipe_name} seed={seed['type']}:{seed['name']} "
             f"({len(collected)} nodes, {len(edges)} edges, {len(globals_)} rules) generated {now()}",
             "# Facts marked conf: medium|low or verified=False MUST NOT be published without verification."]
    by_type: dict[str, list[dict]] = {}
    for n in collected.values():
        by_type.setdefault(n["type"], []).append(n)
    type_order = [seed["type"]] + [t for t in onto.types() if t != seed["type"]]
    for t in type_order:
        for n in sorted(by_type.get(t, []), key=lambda x: x["name"]):
            lines.append(f"## {t}: {n['name']}  {_prov(n)}")
            if n["attrs"]:
                lines.append("  " + _attrs_line(n["attrs"], skip=internal.get(t, set())))
            if n["conflicts"]:
                lines.append("  CONFLICTS: " + json.dumps(n["conflicts"], ensure_ascii=False))
            for (s, r, d), e in edges.items():
                if s == n["id"]:
                    dn = collected.get(d) or store.get(d)
                    lines.append(f"  - {r} -> {dn['type']}: {dn['name']}" + (f" {e['attrs']}" if e["attrs"] else "") + f"  {_prov(e)}")
    if "stock" in recipe.get("summaries", []):
        prods = [n for n in collected.values() if n["type"] == "Product"]
        if prods:
            lines.append("## Stock summary (derived from the stock ledger)")
            for p in prods:
                lines.append(stock_text(stock(store, f"Product:{p['name']}")))
    if globals_:
        lines.append("## Rules in scope")
        for n in sorted(globals_, key=lambda x: (x["type"], x["name"])):
            a = n["attrs"]
            line = f"- {n['type']} {n['name']} [{a.get('category') or a.get('severity','')}]: {a.get('text','')}"
            if a.get("do"):
                line += f" DO: {'; '.join(a['do'])}."
            if a.get("dont"):
                line += f" DON'T: {'; '.join(a['dont'])}."
            lines.append(line)
    if len(lines) > max_lines:
        omitted = len(lines) - max_lines
        lines = lines[:max_lines] + [f"# … {omitted} lines omitted (max_lines={max_lines}); use `kg card <entity>` for detail"]
    return "\n".join(lines)


# ---- path / query ----------------------------------------------------------
def path(store: Store, a_ref: str, b_ref: str, max_hops: int = 4) -> str:
    a, b = store.resolve_any(a_ref), store.resolve_any(b_ref)
    if not a or not b:
        return "endpoint not found"
    prev = {a["id"]: None}
    q = deque([(a["id"], 0)])
    while q:
        cur, d = q.popleft()
        if cur == b["id"]:
            break
        if d >= max_hops:
            continue
        for e in store.edges(cur):
            nxt = e["dst"] if e["src"] == cur else e["src"]
            if nxt not in prev:
                prev[nxt] = (cur, e)
                q.append((nxt, d + 1))
    if b["id"] not in prev:
        return f"no path within {max_hops} hops"
    steps, cur = [], b["id"]
    while prev[cur]:
        p, e = prev[cur]
        arrow = f"-{e['rel']}->" if e["src"] == p else f"<-{e['rel']}-"
        steps.append(f"{arrow} {store.get(cur)['type']}:{store.get(cur)['name']}")
        cur = p
    return f"{a['type']}:{a['name']} " + " ".join(reversed(steps))


def query(store: Store, type_: str, where: dict) -> list[dict]:
    out = []
    for n in store.nodes(type_):
        ok = True
        for k, v in where.items():
            av = n["attrs"].get(k)
            if isinstance(av, list):
                ok = ok and (v in av or (k == "scope" and "all" in av))
            else:
                ok = ok and str(av).lower() == str(v).lower()
        if ok:
            out.append(n)
    return out


# ---- gaps: competency questions 2, 6, 8, 11, 13 as a maintenance report -----
def gaps(store: Store, expiry_days: int = 90, low_stock: int = 3) -> str:
    today = dt.date.today()
    lines = ["# Gaps report"]
    # 2: expiring batches
    exp = []
    for b in store.nodes("Batch"):
        e = b["attrs"].get("expires_on")
        if e and (dt.date.fromisoformat(str(e)) - today).days <= expiry_days:
            prod = [store.get(x["dst"])["name"] for x in store.edges(b["id"], "OF_PRODUCT", "out")]
            exp.append(f"- {b['name']} expires {e} (product: {', '.join(prod)})")
    lines += [f"## Batches expiring within {expiry_days} days ({len(exp)})", *exp]
    # 11: low stock
    low = [f"- {r['product']}: {r['on_hand']:g}" for r in stock(store) if r["status"] == "active" and r["on_hand"] <= low_stock]
    lines += [f"## Active products at or below {low_stock} units ({len(low)})", *low]
    # sellable products with no product photo
    nophoto = [p["name"] for p in store.nodes("Product")
               if p["attrs"].get("status") in ("active", "coming_soon") and not store.edges(p["id"], "DEPICTS", "in")]
    lines += [f"## Sellable products with no product photo ({len(nophoto)})", *[f"- {n}" for n in sorted(nophoto)]]
    # products without a live page
    nop = []
    for p in store.nodes("Product"):
        if p["attrs"].get("status") != "active":
            continue
        pages = [store.get(e["src"]) for e in store.edges(p["id"], "FEATURES", "in")]
        if not any(pg["attrs"].get("status") == "live" for pg in pages):
            nop.append(f"- {p['name']}")
    lines += [f"## Active products with no live product page ({len(nop)})", *nop]
    # 6: keywords not targeted
    kw = [f"- {k['name']} ({k['attrs'].get('intent')}, {k['attrs'].get('priority')})"
          for k in store.nodes("Keyword") if not store.edges(k["id"], "TARGETS", "in")]
    lines += [f"## Keywords no page targets ({len(kw)})", *kw]
    # 8: verified studies not cited anywhere
    st = [f"- {s['name']} (pmid {s['attrs'].get('pmid')})" for s in store.nodes("Study")
          if s["attrs"].get("verified") is True and not store.edges(s["id"], "CITES", "in")]
    lines += [f"## Verified studies cited on no page ({len(st)})", *st]
    unv = [f"- {s['name']}" for s in store.nodes("Study") if s["attrs"].get("verified") is not True]
    lines += [f"## Studies NOT yet verified (cannot be cited) ({len(unv)})", *unv]
    # 13: stale pages — a featured product / claim / batch changed after page.last_updated
    stale = []
    for pg in store.nodes("Page"):
        lu = pg["attrs"].get("last_updated")
        if not lu or pg["attrs"].get("status") != "live":
            continue
        for e in store.edges(pg["id"], direction="out"):
            other = store.get(e["dst"])
            changed = str(other.get("valid_from") or "")[:10]  # fact-change date set in seeds, not ingest time
            if changed and changed > str(lu):
                stale.append(f"- {pg['name']} last_updated {lu} but {other['type']}:{other['name']} changed {changed}")
                break
    lines += [f"## Live pages possibly stale ({len(stale)})", *stale]
    # unresolved conflicts + pending review
    conf = [f"- {n['id']}: {list(n['conflicts'])}" for n in store.nodes() if n["conflicts"]]
    lines += [f"## Nodes with unresolved attribute conflicts ({len(conf)})", *conf]
    rq = store.review_rows()
    lines += [f"## Fusion pairs awaiting review ({len(rq)})"] + [f"- {r['a']} ~ {r['b']} ({r['score']:.2f})" for r in rq]
    return "\n".join(lines)


# ---- export ----------------------------------------------------------------
def export(store: Store, fmt: str = "json") -> str:
    nodes, edges = store.nodes(), store.all_edges()
    if fmt == "json":
        return json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2, default=str)
    if fmt == "triples":
        return "\n".join(f"({store.get(e['src'])['name']})-[{e['rel']}]->({store.get(e['dst'])['name']})" for e in edges)
    if fmt == "mermaid":
        def mid(i): return "n" + str(abs(hash(i)) % 10**8)
        lines = ["graph LR"]
        for n in nodes:
            lines.append(f'  {mid(n["id"])}["{n["type"]}: {n["name"]}"]')
        for e in edges:
            lines.append(f"  {mid(e['src'])} -->|{e['rel']}| {mid(e['dst'])}")
        return "\n".join(lines)
    raise ValueError(fmt)
