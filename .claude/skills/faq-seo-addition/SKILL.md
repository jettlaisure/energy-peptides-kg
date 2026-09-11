---
name: faq-seo-addition
description: Add FAQ items or SEO coverage (keywords, new page proposals) for an Energy Peptides peptide, product or research area, driven by the graph's gaps report. Use when asked for FAQ, SEO, keyword or content-gap work.
---
# FAQ / SEO addition — executes taskgraphs/faq_seo.yaml

1. `uv run kg gaps` → note untargeted keywords and uncited *verified* studies relevant to the seed.
2. `uv run kg context faq_seo "<Type:Name>" --max-lines 200 > $SCRATCH/ctx.md` (seed is a Peptide, Product or ResearchArea).
3. Two workers in parallel (Agent tool, effort low), each with ctx.md only:
   - **w_faq**: 3-5 FAQ items. Question ≤12 words, answer ≤80 words (BR-FAQ). Answers state chemistry facts from the context or what the company does (COA, storage, RUO). Cite only verified=True studies.
   - **w_seo**: for each untargeted keyword: the existing page that should target it, or a proposed new page (title ≤60 chars, slug, meta ≤155, outline). Internal-link suggestions.
4. Two verifiers in separate contexts: **v_compliance** (ComplianceRules in scope faq/all — quote + rule) and **v_facts** (every factual sentence traceable to ctx.md).
5. Merge (you). Max 2 repair rounds. Remove, never soften, failing sentences.
6. Human gate: present the FAQ items, keyword→page mapping, new page proposals, verdicts. Wait for approval.
7. Write-back: FAQ items → `seeds/12_faq.yaml` (status draft, ABOUT edge, SUPPORTED_BY only for verified studies); TARGETS / INCLUDES_FAQ edges → `seeds/13_pages.yaml`; new pages as status planned. Then `uv run kg ingest && uv run kg validate`.
