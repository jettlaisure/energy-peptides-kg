"""Visual map of the graph: one self-contained HTML file (data/graph-map.html) for humans.
Generated from the graph, adds nothing to it, and is excluded from AI context (see .claude/settings.json).
Internal attributes (ontology `internal: true`, e.g. cost_usd) are never written into the map."""
from __future__ import annotations

import json
from pathlib import Path

from .schema import Ontology
from .store import ROOT, Store, now

HERE = Path(__file__).resolve().parent
MAP_PATH = ROOT / "data" / "graph-map.html"


def build(store: Store, onto: Ontology) -> dict:
    internal = {t: {k for k, s in onto.attr_spec(t).items() if (s or {}).get("internal")} for t in onto.types()}
    nodes = [{"id": n["id"], "type": n["type"], "name": n["name"], "conf": n["confidence"], "source": n["source"],
              "aliases": n["aliases"], "valid_to": n["valid_to"],
              "attrs": {k: v for k, v in n["attrs"].items() if k not in internal.get(n["type"], set())}}
             for n in store.nodes()]
    edges = [{"s": e["src"], "t": e["dst"], "rel": e["rel"], "attrs": e["attrs"], "conf": e["confidence"], "source": e["source"]}
             for e in store.all_edges()]
    return {"generated_at": now(), "nodes": nodes, "edges": edges}


def render(store: Store, onto: Ontology, out: Path = MAP_PATH) -> Path:
    template = (HERE / "map_template.html").read_text()
    vendor = (HERE / "vendor" / "cytoscape.min.js").read_text()
    data = json.dumps(build(store, onto), ensure_ascii=False, default=str).replace("</", "<\\/")
    html = template.replace("/*__CYTOSCAPE__*/", vendor).replace("/*__DATA__*/null", data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    return out
