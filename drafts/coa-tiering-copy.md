---
status: approved by Jett and applied 2026-09-21 (deploy and Kashu sync still pending)
date: 2026-09-21
topic: Test only some products; copy claims testing only where a certificate is on file
applies_to: seeds/08_compliance.yaml, seeds/09_brand.yaml, seeds/10_claims.yaml, seeds/12_faq.yaml,
  seeds/13_pages.yaml, site.yaml, web/src (6 files), CLAUDE.md
confidence: medium (model-drafted; wording and the compliance rule need a human check)
---

# Testing only some products: copy and claims changes

## The change in one line
The site stops promising that **every** batch is tested. Instead, each product page says what is true
**for the lot on sale**: tested with a certificate on file, or not yet tested. Site-wide copy only claims
what is true of the tested lots.

## Certificate policy (internal, for buying)

| Tier | Products | Certificate |
|---|---|---|
| 1: own test, every lot | Retatrutide 10/20/30mg, Tirzepatide 10/15/20/30mg, KLOW 80mg | Freedom Diagnostics (US), in the Energy Peptides name |
| 2: supplier's certificate | BPC-157 10mg, BPC-157/TB-500 20mg, GHK-Cu 50/100mg, KPV 10mg, NAD+ 500mg, Tesamorelin 20mg, SS-31 30mg, MOTS-c 10mg | FSD's third-party certificate for the **same lot** |
| 3: none for now | Ipamorelin 10mg, Melanotan I 10mg, Melanotan II 10mg, bacteriostatic water | none |

**What the site shows is driven by data, not by tier.** A product shows the tested wording only when the
lot on sale has a certificate on file (`Batch.coa_status` = `received` or `published`). Tiers decide
what gets bought and tested. The lot data decides what the page says, so a tier 2 product whose FSD
certificate hasn't arrived shows the untested wording automatically.

---

## 1. Compliance rule: `seeds/08_compliance.yaml`, CR-COA-LINK

**Current**
> The site states that batches are tested to a ≥99% purity specification and that certificates are
> available on request. A supplier or third-party certificate must be on file (Batch.coa_status received)
> for every batch of a product before that product is sold. Certificates are not published on the site
> (decision 2026-09-10).

**Proposed**
> A testing, purity or certificate claim may appear only for a product whose lot on sale has a
> certificate on file (Batch.coa_status received or published): either one commissioned by Energy
> Peptides or the supplier's third-party certificate for that same lot. A product without one may be
> sold, but its page, feed entry and marketing make no testing, purity-figure or certificate claim, and
> its page says plainly that a certificate is not yet available. Site-wide copy never says every batch,
> lot or product is tested. 'Tested in the US' is used only where the lot's certificate is from a US
> laboratory. Certificates are not published on the site (decision 2026-09-10).

The basis stays the same: under FTC substantiation rules, a testing claim must be backed by documents on
file. The rule is now applied product by product instead of store-wide.

## 2. Brand rules: `seeds/09_brand.yaml`

**BR-TONE `do`**
- Current: "state the purity specification and that certificates are available on request"
- Proposed: "for a lot with a certificate on file, state the purity specification and that the certificate is available on request; for any other lot, say plainly that a certificate is not yet available"

**BR-PRODUCT-PAGE-STRUCTURE, section order**
- Current: "Specification (paper, includes the purity specification), Quality and testing (paper: the standard testing sentence, certificates on request)"
- Proposed: "Specification (paper; includes the purity specification only when the lot on sale has a certificate on file), Testing & certificates (paper: BR-COA-STATEMENT wording for the lot on sale)"

**BR-COA-STATEMENT**
- Current: "Standard sentence: 'Every batch is tested by HPLC and mass spectrometry against a purity specification of ≥99%. Certificates of analysis are available on request.' …"
- Proposed:
  > Two standard sentences, chosen by the lot on sale (decision 2026-09-21; certificates still not
  > published).
  > **Lot with a certificate on file:** 'This lot has been tested for purity and identity by an
  > independent laboratory against a purity specification of ≥99%. The certificate of analysis is
  > available on request.'
  > **Lot without one:** 'A certificate of analysis is not yet available for the current lot.'
  > The sentence must match what the certificate covers: if it reports identity and content but no
  > purity figure (e.g. the current NAD+ report), use 'This lot's identity and content have been
  > tested by an independent laboratory. The certificate of analysis is available on request.' and
  > show no purity specification.
  > Never state a lot-specific purity figure on the site. Never claim a certificate ships with the
  > product. Never use 'every batch' or 'all products' with a testing claim.

The untested sentence is a plain statement, as BR-TONE asks ("limits stated plainly"). The other option
is to leave the testing section off untested pages entirely. I recommend the plain statement: silence
reads as an oversight, and it makes the "Lot tested" badge mean more.

## 3. Claims: `seeds/10_claims.yaml` (new, all added as `pending`)

| ID | Status | Scope | Text | Condition |
|---|---|---|---|---|
| CL-TEST-LOT | pending | product_page, marketing | This lot has been tested for purity and identity by an independent laboratory. Certificate of analysis available on request. | Lot on sale has coa_status received/published |
| CL-TEST-SITE | pending | site-wide, marketing | Independently tested lots, with certificates of analysis on request. | At least one product on sale has a tested lot |
| CL-TEST-US | pending | product_page, marketing | Tested by an independent US laboratory. | Lot's coa_lab is a US lab (Freedom Diagnostics). Tier 1 only in practice. |
| CL-TEST-NONE | pending | product_page | A certificate of analysis is not yet available for the current lot. | Lot on sale has no certificate |
| CL-TEST-EVERY | **prohibited** | all | Every batch is tested to ≥99% purity. / All our products are lab-tested. | Untrue once any product is untested |
| CL-US-MADE | **prohibited** | all | Made in the USA / US-made / US-sourced peptides. | FSD manufactures in China; testing location is not origin |

CL-TEST-US is the premium US angle we discussed, kept honest: it describes **where the testing happened**,
not where the peptide was made.

## 4. FAQs: `seeds/12_faq.yaml`

**FAQ-3 "Are the products tested?"**
- Current: "Yes. Every batch is tested by HPLC and mass spectrometry against a purity specification of 99% or higher before it is offered. Certificates of analysis are held on file for each batch and are available on request."
- Proposed (68 words):
  > Products marked 'Lot tested' have a certificate of analysis on file for the lot on sale, from an
  > independent laboratory, covering purity by HPLC and identity. Certificates are available on request:
  > tell us the product and the lot number from the vial label. Where a product page says a certificate
  > is not yet available, that lot has not been independently tested, and we make no purity claim for it.

**FAQ-5 (TB-500 vs thymosin beta-4), last sentence**
- Current: "Its identity is confirmed by mass spectrometry in batch testing."
- Proposed: "Where the lot on sale has a certificate on file, the testing laboratory confirms its identity."

**FAQ-7 (BPC-157 / TB-500 blend), last sentence**
- Current: "Both peptides are identity-confirmed by mass spectrometry in batch testing."
- Proposed: "When the lot on sale has a certificate on file, both peptides are identity-confirmed in it, and the certificate is available on request."

## 5. Page metadata: `seeds/13_pages.yaml`

| Page | Current | Proposed |
|---|---|---|
| KLOW 80mg meta description | "…KPV 10 mg per vial. Tested to a ≥99% purity specification. For Research Use Only." | Keep, **but only once the first own-tested KLOW lot is on file** (tier 1). Until then: "…KPV 10 mg per vial. For Research Use Only." |
| BPC-157 / TB-500 meta description | "…10 mg of each peptide per vial, with a per-lot certificate of analysis." | Keep only if FSD's certificate is confirmed to be for the lot on sale. Otherwise: "…10 mg of each peptide per vial. For Research Use Only — Not for Human Consumption." |

## 6. Site copy: `site.yaml` and `web/`

| Where | Current | Proposed |
|---|---|---|
| `site.yaml` testing_line (home, product pages, contact) | Every batch is tested by HPLC and mass spectrometry against a purity specification of ≥99%. Certificates of analysis are available on request. | Products marked 'Lot tested' have a certificate of analysis from an independent laboratory on file for the lot on sale. Certificates are available on request. |
| `Footer.astro` | Research peptides and laboratory compounds, tested batch by batch to a ≥99% purity specification. | Research peptides and laboratory compounds, with independently tested lots and certificates on request. |
| `Base.astro` default meta description | …research peptides tested to a ≥99% purity specification. | …research peptides, independently tested lots, certificates on request. |
| `index.astro` page title | …research peptides, tested to a ≥99% purity specification | …research peptides, independently tested lots |
| `index.astro` hero lede | Tested batch by batch. Defined by composition. Supplied exclusively for laboratory research. | Defined by composition. Supplied exclusively for laboratory research. |
| `index.astro` stat 1 | ≥99% · Purity specification · Tested batch by batch | ≥99% · Purity specification · On independently tested lots |
| `index.astro` stat 2 | HPLC + MS · Purity & identity · Two analytical methods | HPLC + MS · Purity & identity · Independent laboratory |
| `index.astro` stat 3 | COA · Certificates on request · Batch documentation on file | COA · Certificates on request · For every tested lot |
| `index.astro` quality heading | The details matter. Every single batch. | The details matter. Down to the lot. |
| `index.astro` purity block | Analysed by HPLC and mass spectrometry. Certificates of analysis available on request. | Tested lots are analysed by an independent laboratory. Certificates of analysis available on request. |
| `products/index.astro` intro | Prices per vial; every batch tested to a ≥99% purity specification. | Prices per vial. 'Lot tested' marks products with a certificate on file for the lot on sale. |
| `products/index.astro` meta description | …grouped by composition, tested to a ≥99% purity specification. | …grouped by composition, with independently tested lots. |

## 7. Product page and export behaviour (code, not copy)

These make section 6 true automatically instead of relying on anyone remembering:

1. **`kg/site_export.py`**: add `lot_tested: true|false` per product, plus `lot_purity_tested` (false when
   the certificate has no `purity_measured`, as with NAD+), so the page picks the right sentence. `lot_tested` is true when an in-stock lot, or the
   next lot for coming-soon products, has coa_status received/published. Add `lot_tested_us` when that
   lot's `coa_lab` is a US lab.
2. **`products/[slug].astro`, Testing & certificates section**: when lot_tested, show the purity
   specification, methods and the "request" link with the CL-TEST-LOT sentence. Otherwise show the
   CL-TEST-NONE sentence and no purity specification.
3. **`products/[slug].astro`, spec table and JSON-LD**: include "Purity specification" and the
   additionalProperty only when lot_tested (search results shouldn't carry an untested ≥99%).
4. **`products/[slug].astro` chemistry note**: "The identity of every batch is confirmed by mass
   spectrometry." becomes "The identity of tested lots is confirmed by the testing laboratory." (shown
   only when lot_tested).
5. **Catalog cards**: a small "Lot tested" badge when lot_tested (gold outline, one gold element per
   view still holds on the card).
6. **Kashu sync**: if product descriptions carry the testing line, they pick up the new wording on the
   next `kg sync apply`.

## 8. CLAUDE.md

- Current: "Certificates are not published: 'tested to ≥99%, certificates on request'."
- Proposed: "Certificates are not published. Testing is claimed per product, only for a lot with a certificate on file (CR-COA-LINK); never 'every batch'."

---

## What the pages would say today, if applied now

| Product | Lot on sale | Page would say |
|---|---|---|
| Retatrutide 20mg | FSD lot, Freedom certificate (marked "CONFIRM this is the lot in stock") | Tested |
| GHK-Cu 100mg | FSD lot, Janoshik certificate (CONFIRM) | Tested |
| BPC-157 / TB-500 20mg | FSD lot, Freedom certificate, commissioned by another reseller (CONFIRM) | Tested |
| NAD+ 500mg | FSD lot, Janoshik certificate, commissioned by another client (CONFIRM) | **Identity and content only.** The report has no purity figure, so it can't use the "purity and identity" sentence (see below) |
| **BPC-157 10mg** | **no certificate** | **Not yet available** |
| **GHK-Cu 50mg** | **no certificate** | **Not yet available** |
| Bacteriostatic water | no certificate | No testing section (not a peptide) |

**Heads-up:** under today's rule, BPC-157 10mg and GHK-Cu 50mg shouldn't be on sale, because no
certificate is on file for them while the site says every batch is tested. Either change applies it:
this new rule, or getting FSD's certificates for those two lots (both are tier 2, so ask FSD first).

## Before applying
1. Jett approves or edits the wording above. The CR-COA-LINK text should get a human check, since it is
   the compliance basis.
2. Confirm the four "CONFIRM this is the lot in stock" certificates match the vials on hand. Otherwise
   those pages drop to "not yet available" too.
3. Then: edit seeds → `kg ingest` → `kg validate` → site export and code changes (section 7) → `npm run build`
   → preview → human gate before deploy → `kg sync plan|apply --adapter kashu`.
