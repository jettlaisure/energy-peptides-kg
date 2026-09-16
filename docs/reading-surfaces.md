# Secondary-page surface refinement

Approved by Jett on 2026-09-16: retain the homepage hero, keep navy as the brand foundation, quiet competing accents, and introduce purposeful light reading sections on product and FAQ pages. This approval expands the older brand rule that reserved paper surfaces for documents and forms.

Product pages retain navy purchase areas and a prominent gold Add to cart button. Overview, specifications, testing, research, FAQs, and the supporting sidebar share a warm off-white reading area with dark text and restrained rules. The sidebar and document sections no longer appear as separate coloured cards.

The FAQ uses a navy introduction followed by an off-white question area. Category headings sit alongside the questions on desktop and above them on mobile. Native accordion behavior and existing anchors are preserved.

The catalog remains navy. Composition navigation becomes understated text links, filter controls share the page background, prices use neutral text, and product arrows become gold on hover instead of competing for attention at rest. These changes are scoped to the catalog; shared homepage cards and the hero are unchanged.

`web/src/styles/reading.css` scopes light colours, link contrast, focus outlines, FAQ controls, and specification tables to `.reading-surface`. It is imported only by product detail and FAQ pages. Product data, policies, purchasing logic, and the home hero were not modified.

Validation: production build, graph ingest/validation, and 21 Python tests passed. Browser review covered desktop catalog, product details and FAQ; FAQ expansion; BPC157 search returning three matching products; 390 px mobile layouts; and the long BPC-157 / TB-500 heading at 320 px without horizontal overflow. Physical-device testing and Lighthouse were not performed.
