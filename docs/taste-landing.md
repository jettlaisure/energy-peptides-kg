# Taste landing-page redesign

Design read: a premium research-supply storefront for laboratory buyers, using the existing navy/gold identity and Satoshi typography. Native Astro and CSS; design variance 6, motion 3, density 3.

## Audit and decisions

The existing homepage repeated boxed composition tiles, numbered section labels and a full multi-row catalog before the testing and FAQ sections. The redesign retains the section order, routes, anchors, navigation, logo, product data and metadata, while changing the composition and rhythm:

- Two-line hero, larger product photograph, restrained type weight and a single prominent catalog button.
- Composition directory in two columns with a sticky introduction on desktop.
- Native horizontal catalog rail with keyboard focus, touch scrolling, previous/next buttons and disabled boundary states. All compounds remain rendered and accessible without JavaScript. Available compounds appear first; stock data is unchanged.
- Larger purity specification and separate handling/research-use details.
- More generous spacing, lighter product-card framing and a shorter header.

The taste skill's generic light/dark requirement is overridden by the established dark-ground brand specification. Existing legal wording and SEO metadata are preserved, including their punctuation. No dependency or product-data changes were made. No sales, urgency, testimonial or health-outcome claims were added. Conversion improvement has not been measured.

## Validation

- Production build passes (Cloudflare prerender included).
- Graph validation passes; 21 Python tests pass.
- In-app browser: no horizontal document overflow at 320, 390, 768 and 1440 pixels.
- In-app browser: mobile menu opens with Enter and closes with Escape; catalog CTA navigates; punctuation-tolerant BPC157 search returns three products; nonexistent search shows empty state; collection next button scrolls and enables previous.
- Desktop and mobile visual inspection performed. Desktop screenshot supplied separately.
- Playwright's eight automated UI tests could not execute: Chromium launch is blocked by this environment's sandbox. They are not reported as passing. Lighthouse is likewise unverified.
- Existing dependency installation reports five high-severity audit findings; no dependency upgrades were mixed into this design change.

## Local preview

Build with `npm run build` in `web`, then serve `web/dist/client` for static UI inspection. The static preview does not run checkout APIs.

Initially verified locally. The landing redesign and refined interactive hero vial were subsequently deployed with Jett's approval to https://preview.energypeptides.us on 2026-09-16 (application commit `360aff4`). See `docs/hero-vial.md` for the deployment version and verification. No live payment was performed.
