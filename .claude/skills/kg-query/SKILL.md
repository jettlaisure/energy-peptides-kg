---
name: kg-query
description: Answer any question about Energy Peptides (products, peptides, stock, claims, rules, pages, SEO) from the knowledge graph using progressive disclosure — never dump the graph into context.
---
# Query the Energy Peptides knowledge graph

Disclosure ladder — stop at the first rung that answers the question:
1. `uv run kg index` — what exists (one line per type).
2. `uv run kg card "<Type:Name>"` — one entity with its 1-hop edges and provenance.
3. `uv run kg context <recipe> "<Type:Name>"` — the task bundle (`uv run kg recipes` lists recipes).
4. `uv run kg path "<A>" "<B>"`, `uv run kg query <Type> --attr value`, `uv run kg stock [product] --events`, `uv run kg gaps`.

Rules:
- Quote facts with their provenance tag `[src: …; conf: …]`. A fact with conf medium/low is reported as "unverified".
- A Study with verified=False may be mentioned as "in the graph, unverified" but never cited as support.
- If the answer needs a type or relation the ontology lacks, say so and point at `ontology.yaml` + `competency_questions.md` — do not improvise structure.
- Never read `data/graph.db` directly and never `kg export` into context unless the user asks for the whole graph.
