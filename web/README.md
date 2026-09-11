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
Then in the Cloudflare dashboard attach `energypeptides.us` to the worker (Custom Domains). Switch `PAYMENT_MODE` in
`wrangler.jsonc` to `tagada` and `PUBLIC_PAYMENT_MODE` in `.env` to `tagada` when going live; keep `TAGADA_ENV=test`
until a sandbox order has round-tripped.

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
