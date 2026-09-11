"""Stages 4-6 for UNSTRUCTURED sources: LLM extraction constrained by the ontology.
Two passes per chunk (entities, then relations between recognised entities only).
Output goes to the STAGING table, never straight into the graph — stage 7 gates it."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .schema import Ontology
from .store import Store

MODEL = "claude-opus-5"

Conf = Literal["high", "medium", "low"]


class KV(BaseModel):
    key: str
    value: str


class EntityOut(BaseModel):
    surface: str = Field(description="exact text as it appears")
    canonical: str = Field(description="canonical name per the ontology's canonical rules")
    type: str
    attrs: list[KV] = Field(default_factory=list)
    evidence: str = Field(description="verbatim sentence containing the mention")
    confidence: Conf


class EntityBatch(BaseModel):
    entities: list[EntityOut]
    candidates: list[str] = Field(default_factory=list, description="recurring concepts that fit no ontology type")


class RelationOut(BaseModel):
    src: str = Field(description="'Type:Canonical' of a recognised entity")
    rel: str
    dst: str = Field(description="'Type:Canonical' of a recognised entity")
    attrs: list[KV] = Field(default_factory=list)
    evidence: str = Field(description="verbatim sentence that ASSERTS the relation (co-occurrence is not assertion)")
    confidence: Conf


class RelationBatch(BaseModel):
    relations: list[RelationOut]
    candidate_relations: list[str] = Field(default_factory=list, description="real but un-modelled relations, as 'A VERB B'")


def chunk_text(text: str, size: int = 6000, overlap: float = 0.12) -> list[str]:
    if len(text) <= size:
        return [text]
    step = int(size * (1 - overlap))
    return [text[i:i + size] for i in range(0, len(text), step)]


def _client():
    import anthropic
    return anthropic.Anthropic()


def _parse(client, system: str, user: str, schema):
    resp = client.messages.parse(
        model=MODEL, max_tokens=16000, thinking={"type": "adaptive"},
        system=system, messages=[{"role": "user", "content": user}], output_format=schema)
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"model declined extraction: {getattr(resp, 'stop_details', None)}")
    return resp.parsed_output


ENTITY_SYSTEM = """You are extracting knowledge for a graph with this ontology:
{ontology}

Rules:
- Only types from the ontology. Recurring concepts that fit no type -> list under candidates.
- Evidence must be a verbatim quote containing the mention.
- Do not merge distinct mentions; deduplication happens later.
- attrs: only attribute names the ontology lists for that type, values as strings.
- This is a research-peptide vendor. Do not invent facts; if a value is not in the text, omit it."""

RELATION_SYSTEM = """You are extracting relations for a graph with this ontology:
{ontology}

Recognised entities in this text (use ONLY these as endpoints, written as 'Type:Canonical'):
{entities}

Rules:
- Assert only relations the evidence sentence states directly. Co-occurrence is not assertion.
- Only relation names from the ontology, and only where domain/range fit.
- Real but un-modelled relations -> candidate_relations."""


def extract_text(store: Store, onto: Ontology, text: str, source: str, client=None) -> dict:
    client = client or _client()
    stats = {"entities": 0, "relations": 0, "rejected": 0, "candidates": 0, "chunks": 0}
    onto_text = onto.prompt_text()
    for ci, chunk in enumerate(chunk_text(text)):
        stats["chunks"] += 1
        src = f"{source}#chunk{ci}"
        ents: EntityBatch = _parse(client, ENTITY_SYSTEM.format(ontology=onto_text), chunk, EntityBatch)
        recognised = []
        for e in ents.entities:
            if not onto.has_type(e.type):
                stats["rejected"] += 1
                continue
            attrs = {kv.key: kv.value for kv in e.attrs}
            attrs = {k: v for k, v in attrs.items() if k in onto.attr_spec(e.type)}
            existing = store.resolve(e.type, e.canonical) or store.resolve(e.type, e.surface)
            payload = {"type": e.type, "canonical": existing["name"] if existing else e.canonical,
                       "surface": e.surface, "attrs": attrs, "aliases": [e.surface] if e.surface != e.canonical else [],
                       "resolved_to": existing["id"] if existing else None}
            store.stage("node", payload, src, e.evidence, e.confidence)
            recognised.append(f"{e.type}:{payload['canonical']}")
            stats["entities"] += 1
        for c in ents.candidates:
            store.add_candidate("entity", c, src); stats["candidates"] += 1
        if not recognised:
            continue
        rels: RelationBatch = _parse(client, RELATION_SYSTEM.format(ontology=onto_text, entities="\n".join(sorted(set(recognised)))),
                                     chunk, RelationBatch)
        rec_types = {r.split(":", 1)[1].lower(): r.split(":", 1)[0] for r in recognised}
        for r in rels.relations:
            try:
                st, sn = r.src.split(":", 1); dt_, dn = r.dst.split(":", 1)
            except ValueError:
                stats["rejected"] += 1; continue
            if r.src not in recognised or r.dst not in recognised or onto.check_edge(r.rel, st, dt_):
                stats["rejected"] += 1; continue  # never let relation extraction invent entities
            store.stage("edge", {"src": r.src, "rel": r.rel, "dst": r.dst, "attrs": {kv.key: kv.value for kv in r.attrs}},
                        src, r.evidence, r.confidence)
            stats["relations"] += 1
        for c in rels.candidate_relations:
            store.add_candidate("relation", c, src); stats["candidates"] += 1
        store.commit()
    return stats


def extract_file(store: Store, onto: Ontology, path: Path, client=None) -> dict:
    return extract_text(store, onto, Path(path).read_text(), source=str(path), client=client)
