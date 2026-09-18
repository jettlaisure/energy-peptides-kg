# Supporting-page design refinement

Applied the user-supplied `redesign-existing-projects` skill on 2026-09-16. The user explicitly protected the home hero; its markup, model, scripts, header, global CSS and design tokens are unchanged.

## Audit and decisions

- Catalog groups lacked a strong relationship between their heading and products. On desktop, composition headings now occupy a narrow left column with consistently sized product cards alongside them. Mobile returns to a single column.
- Product cards repeated long uppercase composition labels and pill-shaped status indicators. Sentence-case labels, plain status text, restrained arrows, and medium-weight prices reduce competing emphasis. Long product names can wrap. Keyboard focus receives the same card outline as hover.
- Policy pages used a narrow, undifferentiated dark text column with heavy headings. A shared policy layout introduces the previously approved warm reading surface, a clear type hierarchy, comfortable line lengths, and current-page navigation. All four policy bodies are preserved verbatim, including existing draft notices.
- The cart empty state was a single sentence. It now has a composed heading, a small bag illustration, and a catalog action. Order totals use a simple dividing rule rather than another framed panel.
- FAQ categories now have direct navigation. Reading surfaces have more comfortable answer leading and restrained hover feedback.

Satoshi, the existing brand palette, native scrolling, native FAQ disclosure and reduced-motion support are retained. No decorative libraries, invented claims, artificial urgency, fabricated dates or stock imagery were added. ProductCard refinements also appear in the homepage collection below the protected hero.

## Validation

- Production build passed; graph ingest/validate clean; 21 Python tests passed.
- Desktop browser inspection: catalog grouping and policy layout.
- 390px mobile inspection: policy, empty cart, catalog search, FAQ category navigation and long-name product detail; checked no horizontal overflow on policy/catalog/FAQ/product detail.
- Catalog search returned 3 of 21 for BPC157, unmatched search displayed the empty state, and reset restored all 21.
- Programmatic comparison confirmed all four policy bodies unchanged, and no diff in protected homepage/hero/model/shared-style/header files.

Deployment target remains the preview domain only.
