# energypeptides.us — storefront

Astro 7 static site on Cloudflare Pages/Workers, rendered from the knowledge graph (`../seeds` → `kg export --format site`
→ `src/data/catalog.json`). Cart is client-side; checkout, 3DS return, payment status and the Kashu webhook are
server routes (`src/pages/api/*`). Orders live in Cloudflare D1 (`schema.sql`); PII never enters the graph.

## Local
```bash
npm install
cp .dev.vars.example .dev.vars           # PAYMENT_MODE=stub until the Kashu account is live
npm run db:migrate:local                 # creates the local D1 tables
npm run preview                          # builds (regenerates the catalog) and serves on :8788 via wrangler
```
Test mode approves every order without a card. `/api/health` reports mode, catalog age and DB state.

## Storefront UI checks

```bash
npm ci
npx playwright install --with-deps chromium   # first run only
npm run build
npm run test:ui
```

The Playwright suite serves `dist/client/` using Python on localhost:4322. It checks responsive layouts,
mobile navigation (including without JavaScript), catalog search/stock filters, and browser-side cart
behavior. It does **not** call payment APIs or create orders. The knowledge graph must be rebuilt first
on a fresh checkout (`cd .. && uv run kg rebuild`).

For local review screenshots, serve `dist/client/` on localhost:4322, then run
`node tests/preview.mjs`. Images are saved to the gitignored `test-results/previews/` directory.

See `../docs/storefront-refresh.md` for the design scope and items requiring owner review before launch.

## Deploy (first time)
```bash
npx wrangler login                                   # your Cloudflare account, in a browser
npx wrangler d1 create energy-peptides-orders        # paste the database_id into wrangler.jsonc
npm run db:migrate                                   # remote tables
npx wrangler secret put TAGADA_API_KEY               # only once the Kashu account is active
npx wrangler secret put TAGADA_STORE_ID
npx wrangler secret put TAGADA_WEBHOOK_SECRET        # from creating the webhook endpoint
npm run deploy
```
Switch `PAYMENT_MODE` in `wrangler.jsonc` to `tagada` and `PUBLIC_PAYMENT_MODE` in `.env` to `tagada` when going live;
keep `TAGADA_ENV=test` until a sandbox order has round-tripped.

## Domains
`energypeptides.us`, `www.energypeptides.us` and `preview.energypeptides.us` are attached in the Cloudflare dashboard
under **Workers & Pages → energy-peptides → Settings → Domains & Routes**, and deliberately **not** in
`wrangler.jsonc`. `wrangler deploy` reads a `routes` list as the complete set of triggers, so deploying a branch whose
copy of that file predates a domain detaches it and deletes its DNS record — that is how the site went down on
2026-09-18. With no `routes` key, wrangler leaves the triggers alone and prints the attached domains for confirmation,
so any branch is safe to deploy. Add or remove a domain in the dashboard, never in the config.

## Every content or inventory change
```bash
cd .. && uv run kg ingest && uv run kg validate     # graph
cd web && npm run deploy                             # regenerates catalog.json and redeploys
```
Paid orders flow back into the graph's ledger with `uv run kg orders pull --remote --apply && uv run kg ingest`.
Product copy approved through `/new-product-page` lands in `../site/pages/products/<slug>.md` and is rendered in the
product's Overview automatically.

## Payment paths
`src/server/payments/stub.ts` (test) and `src/server/payments/tagada.ts` (Kashu / TagadaPay direct S2S:
create-from-token → optional 3DS → process). Selection is by `PAYMENT_MODE`. Webhook verification accepts both
Tagada envelope styles (`src/server/webhook.ts`).
