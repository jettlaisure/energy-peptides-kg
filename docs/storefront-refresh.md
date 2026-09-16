# Storefront refresh — review draft

Branch: `design/storefront-refresh`. This is a local design iteration, not approval to publish or deploy.

## Preserved

- Graph-generated catalog, product prices, availability, and all existing URLs.
- Homepage sequence: introduction, composition classes, product catalog, standards, FAQ.
- Satoshi typography, navy/gold tokens, original brand mark, and existing product photography.
- Research-only wording, composition-based browsing, purchaser attestation, and payment integration.
- No testimonials, health outcomes, sales rankings, artificial urgency, or discounts added.

## Changes

- Product-led split homepage hero, clear catalog CTA, and visible testing/documentation summary.
- More distinct section hierarchy, composition cards, and product cards with explicit detail links.
- Shipping threshold surfaced from `site.yaml`, not hardcoded in UI copy.
- Mobile navigation using native `details`, with keyboard/Escape behavior and no-JavaScript fallback.
- Search by product/composition/SKU and in-stock filter on the catalog, with result counts, empty states,
  reset controls, and punctuation-tolerant matching. Catalog remains visible without JavaScript.
- Product-page shipping, specifications, and certificate links adjacent to purchasing controls.
- Clearer cart summary, continue-browsing link, and corrected styling for dynamically rendered cart rows.
- Larger interactive targets, skip-to-content link, sticky-header anchor offset, reduced-motion support,
  and consistent hidden-state handling.

## Owner review required before launch

1. **Repository confidentiality:** the existing project instructions identify internal costs, supplier
   documents, and certificates as private. Restore private visibility and revoke the token shared in chat.
2. **Contact address:** `site.yaml` still has `TODO@energypeptides.us`. Replace with a monitored address;
   certificate request links depend on it. No address was invented in this refresh.
3. **Claims and specifications:** existing testing, purity, storage, and shipping statements still need
   business-owner verification. This design pass is not scientific verification or legal approval.
4. **Payment readiness:** Cloudflare configuration points at Tagada test mode, and the README describes
   activation steps. Verify sandbox payments, shipping/tax policies, and live credentials separately.
5. **Dependencies:** npm reported four high-severity findings during installation. Review `npm audit`
   before deployment; dependency upgrades were not mixed into this visual refresh.
6. **Photography:** existing product photos use light backgrounds, unlike the original brand reference.
   They have been retained, not recolored or replaced. A separate approved photography pass can unify them.

## Validation

Run graph validation and Python tests from the root, then production build and UI tests in `web/`.
See `web/README.md` for commands. UI tests use only local static output and localStorage; payment APIs,
real orders, deployment, and conversion-rate measurement are outside their scope.
