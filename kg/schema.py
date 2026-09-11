"""Stage 3: ontology loading + domain/range validation. The ontology file is the source of truth."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from .store import ROOT, Store

ONTOLOGY_PATH = ROOT / "ontology.yaml"


class Ontology:
    def __init__(self, path: Path | str = ONTOLOGY_PATH):
        self.path = Path(path)
        self.raw = yaml.safe_load(self.path.read_text())
        self.entities: dict = self.raw.get("entities", {})
        self.events: dict = self.raw.get("events", {})
        self.relations: dict = self.raw.get("relations", {})
        self.recipes: dict = self.raw.get("recipes", {})
        self.canonical_rules: dict = self.raw.get("canonical_rules", {})

    # ---- types -------------------------------------------------------------
    def types(self) -> dict:
        return {**self.entities, **self.events}

    def has_type(self, t: str) -> bool:
        return t in self.types()

    def attr_spec(self, t: str) -> dict:
        return (self.types().get(t) or {}).get("attrs", {}) or {}

    # ---- validation --------------------------------------------------------
    def check_node(self, type_: str, attrs: dict) -> list[str]:
        """Returns warnings (unknown attrs, enum/type violations). Unknown type is an error string too."""
        issues = []
        if not self.has_type(type_):
            return [f"unknown entity type {type_!r}"]
        spec = self.attr_spec(type_)
        for k, v in (attrs or {}).items():
            if k not in spec:
                issues.append(f"{type_}: attribute {k!r} not in ontology")
                continue
            s = spec[k] or {}
            enum = s.get("enum")
            if enum and v not in enum:
                issues.append(f"{type_}.{k}={v!r} not in enum {enum}")
            t = s.get("type")
            if t == "number" and not isinstance(v, (int, float)):
                issues.append(f"{type_}.{k}={v!r} should be a number")
            if t == "boolean" and not isinstance(v, bool):
                issues.append(f"{type_}.{k}={v!r} should be a boolean")
            if t == "list" and not isinstance(v, list):
                issues.append(f"{type_}.{k}={v!r} should be a list")
            if t == "date":
                try:
                    dt.date.fromisoformat(str(v))
                except ValueError:
                    issues.append(f"{type_}.{k}={v!r} should be an ISO date")
        return issues

    def check_edge(self, rel: str, src_type: str, dst_type: str) -> str | None:
        """Domain/range check. Returns an error string or None. This single check kills most
        hallucinated structure (stage 5 rule)."""
        spec = self.relations.get(rel)
        if spec is None:
            return f"unknown relation {rel!r}"
        if src_type not in spec["domain"]:
            return f"{rel}: domain is {spec['domain']}, got {src_type}"
        if dst_type not in spec["range"]:
            return f"{rel}: range is {spec['range']}, got {dst_type}"
        return None

    # ---- prompt serialisation (stages 4-6) -----------------------------------
    def prompt_text(self) -> str:
        lines = ["ENTITY TYPES:"]
        for t, s in self.types().items():
            ex = ", ".join(map(str, s.get("examples", [])))
            lines.append(f"- {t}: {s.get('desc','')} (e.g. {ex})")
        lines.append("\nRELATION TYPES (domain -> range):")
        for r, s in self.relations.items():
            lines.append(f"- {r}: {'|'.join(s['domain'])} -> {'|'.join(s['range'])}" + (f" — {s['note']}" if s.get("note") else ""))
        lines.append("\nCANONICAL NAME RULES:")
        for t, rule in self.canonical_rules.items():
            lines.append(f"- {t}: {rule}")
        return "\n".join(lines)


def validate_graph(store: Store, onto: Ontology) -> list[str]:
    """Stage 7 gate for the stored graph: every node's type/attrs and every edge's domain/range."""
    issues: list[str] = []
    types = {}
    for n in store.nodes():
        types[n["id"]] = n["type"]
        for w in onto.check_node(n["type"], n["attrs"]):
            issues.append(f"node {n['id']}: {w}")
        if not n.get("source"):
            issues.append(f"node {n['id']}: missing provenance source")
    for e in store.all_edges():
        st, dt_ = types.get(e["src"]), types.get(e["dst"])
        if st is None or dt_ is None:
            issues.append(f"edge {e['src']} -{e['rel']}-> {e['dst']}: dangling endpoint")
            continue
        err = onto.check_edge(e["rel"], st, dt_)
        if err:
            issues.append(f"edge {e['src']} -{e['rel']}-> {e['dst']}: {err}")
    return issues
