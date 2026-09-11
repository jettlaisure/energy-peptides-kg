---
name: new-product-page
description: Create or refresh an Energy Peptides product page from the knowledge graph, with parallel drafting, separate compliance/brand/fact verifiers, and a human gate before anything is published. Use when asked to build, write, or update a product page.
---
# New / refreshed product page — executes taskgraphs/product_page.yaml

Input: a product, e.g. "BPC-157 10mg". Scratch dir: use the session scratchpad.

## 1. Context (single call — this is the whole context budget for the page)
```
uv run kg context product_page "Product:<name>" --max-lines 250 > $SCRATCH/ctx.md
```
If it prints "not found": stop, tell the user to add the product to `seeds/03_products.yaml` (schema in `ontology.yaml`) and run `uv run kg ingest`. Do not invent a product.

## 2. Fan-out — three workers in parallel (Agent tool, `subagent_type: general-purpose`, effort low)
Each worker gets: the full text of `$SCRATCH/ctx.md`, its brief below, and the instruction
"Use only facts present in the context. Output markdown only." Nothing else.
- **w_copy** → `$SCRATCH/copy.md`: sections *Overview* (2-3 sentences) and *Research background*. Only Claims with status=approved. Only Study nodes with verified=True may be cited; if none, the section says research citations are pending verification. Name the model (rodent / in vitro / human) for every study mentioned.
- **w_specs** → `$SCRATCH/specs.md`: *Specifications* table (sequence, formula, MW, CAS, form, size, purity spec, price) and *Quality and COA* (use BR-COA-STATEMENT text; link the newest published COA asset). Append "(verify)" to any value whose provenance says conf: medium or low.
- **w_seo_faq** → `$SCRATCH/seo.md`: meta title (≤60 chars, ends "| Energy Peptides"), meta description (≤155), H1, slug (from Product.slug), internal links (research-area page, blends sharing the peptide), and 2-4 FAQ items chosen from existing FAQItems by id; new ones marked `NEW` with question + answer.

## 3. Verify — three separate contexts, three different questions (Agent tool, in parallel)
Each verifier gets `$SCRATCH/ctx.md` + the three drafts and returns `PASS` or a list of `FAIL: "<quoted sentence>" — <rule id or reason>`.
- **v_compliance**: "Does any sentence violate a ComplianceRule listed under *Rules in scope*?"
- **v_brand**: "Does any sentence break a BrandRule (tone, vocabulary, structure, formatting, seo)?"
- **v_facts**: "Is every factual statement traceable to a line in ctx.md? An untraceable statement is a FAIL even if true."

## 4. Merge — you are the single owner
Assemble in BR-PRODUCT-PAGE-STRUCTURE order into `site/pages/products/<slug>.draft.md` with front-matter
(title, meta_description, slug, product, generated_at). Apply verifier fixes: anything failing v_facts or
v_compliance is **removed**, not softened. Re-run only the verifiers that failed. **Max 2 repair rounds**; if
still failing, stop and report which sentences and rules are blocking.

## 5. Human gate — never skip
Present: path of the draft, the three final verdicts, the "(verify)" flags, and NEW FAQ items. Ask for
approval. Do NOT rename the draft to a live page, deploy, or push. Wait.

## 6. Write-back (after explicit approval)
1. Rename `.draft.md` → `.md`.
2. Append the Page to `seeds/13_pages.yaml` (status: live, last_updated: today, file path) with edges:
   FEATURES product, COVERS peptide(s), BELONGS_TO research area, TARGETS keywords, INCLUDES_FAQ ids,
   USES image + COA assets, LINKS_TO internal links.
3. NEW FAQ items → `seeds/12_faq.yaml` with status draft and an ABOUT edge.
4. `uv run kg ingest && uv run kg validate`. Both must be clean.

Guardrails: max 3 workers, 3 verifiers, 2 repair rounds; only you write the page file; never load the whole graph.
