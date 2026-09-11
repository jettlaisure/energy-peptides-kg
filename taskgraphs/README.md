# Task graphs

Nodes are jobs; an arrow exists only when a job needs another job's *result*. Every graph here is the
diamond: **context → parallel workers → separate verifiers → one merge owner → human gate → write-back**.

Rules that apply to every graph (from the graph-engineering skill):
1. Workers receive ONLY the recipe context file, never the whole graph (progressive disclosure).
2. Verifiers run in separate contexts and each asks a *different* question (compliance / brand / facts).
3. One owner merges. Max 2 repair rounds, then stop and report.
4. The human gate sits on the irreversible edge (publish, deploy, stock adjustment), not on every step.
5. One writer per file. Hard cap on workers (3) and verifiers (3).
6. Write-back goes through seeds/ + `kg ingest` + `kg validate` — never by editing the database directly.

Graphs: `product_page.yaml`, `faq_seo.yaml`, `marketing_copy.yaml`, `inventory.yaml`.
Executable form: the matching skill under `.claude/skills/` — Claude Code runs the graph.
