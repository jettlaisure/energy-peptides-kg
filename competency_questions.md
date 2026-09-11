# Competency questions (stage 1 + stage 3 spec, and the test suite)

The graph exists to answer these. Each maps to a `kg` command and a test in `tests/test_competency.py`.
If a future question cannot be pathed through `ontology.yaml`, that is the signal to add a type or relation.

## Stage 1 value test
Single-hop lookups ("what is the price of X") would fit a spreadsheet. The questions below are
multi-hop, entities recur across product pages, FAQs, marketing, batches and studies, and the
relationships (which claim is backed by which study under which rule) ARE the data. Graph wins.

| # | Question | Path through the ontology | Command |
|---|----------|---------------------------|---------|
| 1 | Which products contain peptide X, and what is on hand per batch? | Peptide ←CONTAINS– Product ←OF_PRODUCT– Batch ←AFFECTS– InventoryEvent | `kg stock` / `kg context inventory` |
| 2 | Which batches expire within 90 days, and which products do they back? | Batch.expires_on, Batch –OF_PRODUCT→ Product | `kg gaps` |
| 3 | Which approved claims can a product page for X use, and which studies support each? | Product –CONTAINS→ Peptide ←ABOUT– Claim –SUPPORTED_BY→ Study | `kg context product_page` |
| 4 | Which brand rules apply when writing a product page / FAQ / email? | BrandRule.scope | `kg query BrandRule --scope product_page` |
| 5 | Which compliance rules constrain copy in channel C? | ComplianceRule.scope | `kg query ComplianceRule --scope ads` |
| 6 | Which keywords have no page targeting them? | Keyword ←TARGETS– Page (absent) | `kg gaps` |
| 7 | Which FAQ items exist about X, and which pages include them? | Peptide ←ABOUT– FAQItem ←INCLUDES_FAQ– Page | `kg context faq_seo` |
| 8 | Which verified studies investigate X but are cited on no page? | Study –INVESTIGATES→ Peptide; Study ←CITES– Page (absent) | `kg gaps` |
| 9 | Which supplier supplied the batch behind COA Z? | Asset ←HAS_COA– Batch –SUPPLIED_BY→ Supplier | `kg card` / `kg path` |
| 10 | What were the stock movements for product P? | Product ←OF_PRODUCT– Batch ←AFFECTS– InventoryEvent | `kg stock P --events` |
| 11 | Which products in research area Y are low on stock? | ResearchArea ←BELONGS_TO– Product ... InventoryEvent | `kg gaps` |
| 12 | Which assets (images, COAs) can a page for product P use? | Product –USES→ Asset; Batch –HAS_COA→ Asset | `kg context product_page` |
| 13 | Which live pages feature a product whose facts changed after the page was last updated? | Page.last_updated vs Product/Batch/Claim extracted_at | `kg gaps` |
| 14 | What is the complete, minimal context needed to write a product page for X? | recipe `product_page` | `kg context product_page X` |
| 15 | Which products share a peptide (blends), for cross-linking? | Product –CONTAINS→ Peptide ←CONTAINS– Product | `kg card Peptide:X` |
| 16 | Is claim text T allowed, and under which rule? | Claim –GOVERNED_BY→ ComplianceRule | `kg query Claim --status prohibited` |
