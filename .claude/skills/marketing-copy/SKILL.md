---
name: marketing-copy
description: Write compliant, on-brand Energy Peptides marketing copy (email, social, ads) for a product or research area from the knowledge graph, with compliance and brand verifiers and a human gate before sending or posting.
---
# Marketing copy — executes taskgraphs/marketing_copy.yaml

Input: seed (Product or ResearchArea) and channel (email | social | ads).

1. `uv run kg context marketing "<Type:Name>" --max-lines 150 > $SCRATCH/ctx.md`
2. Two workers in parallel (Agent tool, effort low), ctx.md only, BR-MARKETING limits (email ≤120 words, social ≤280 chars, one CTA):
   - **w_a** product-fact angle: what it is, size, purity spec, COA, price, in stock (from the stock summary).
   - **w_b** research-area angle: approved Claims only, model named, no outcomes.
3. Two verifiers in separate contexts: **v_compliance** (effects language, testimonials, brand names, dosing, approval implication — quote + rule) and **v_brand** (length, single CTA, hype/urgency, vocabulary — quote + rule).
4. Merge: keep passing variants; max 2 repair rounds; remove failing sentences.
5. Human gate: show the copy and verdicts. Never send, schedule or post.
6. No write-back (copy is not graph knowledge). If you needed a claim that does not exist, add it to `seeds/10_claims.yaml` as `status: pending` and say so.
