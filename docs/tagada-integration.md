# Kashu / TagadaPay integration notes (gathered 2026-09-09 from public docs.tagada.io)

Kashu Pay's merchant dashboard is a white-label of **TagadaPay** ("TagadaPay handles all routing internally").
The store therefore integrates with Tagada's SDK and REST API. Nothing here contains credentials.

## Facts that shape the design
| Topic | What the docs say | Consequence for us |
|---|---|---|
| Base URL | prod `https://api.tagada.io/api/public/v1`; sandbox `https://app.tagadapay.dev/api/public/v1` | Confirm from the Kashu dashboard whether keys point at api.tagada.io or a Kashu-branded host |
| Auth | `Authorization: Bearer <key>`; dashboard keys from Settings → API Keys / Access Tokens; partner keys `tp_sk_…` | Server-side only, in Cloudflare env var `TAGADA_API_KEY` |
| Node SDK | `@tagadapay/node-sdk`: `new Tagada({apiKey, baseUrl, idempotencyKey})`; resources `.list/.retrieve/.create/.update/.del` | Use from Pages Functions (Node-compatible Workers) |
| Products | `products.create({storeId, name, description, active, isShippable, isTaxable, variants:[{name, sku, active, default, inStock, grams, imageUrl, prices:[{currencyOptions:{USD:{amount: cents}}, recurring:false, default:true}]}]})` → `prod_…`, variant ids | `kg sync --adapter tagada`: graph Product → Tagada product (family) + variant (SKU). Amounts in **cents**. |
| Inventory | variants have only `inStock: boolean`; no quantity field | Stock stays in the graph ledger; sync pushes `inStock = on_hand > 0` |
| Checkout | `checkout.createSession({storeId, items:[{variantId, quantity}], currency, checkoutUrl, customerEmail…, metadata.cartCustomAttributes, returnUrl})` → `{redirectUrl, checkoutToken, checkoutRoutePublished}` | If `checkoutRoutePublished` is true Tagada hosts checkout: our site just redirects. Otherwise build our own checkout with `@tagadapay/headless-sdk` + `@tagadapay/core-js` tokenization (3DS handled by `processPayment`). Decide after first sandbox call. |
| Metadata | `metadata.cartCustomAttributes` come back on the order and in `order/paid` | Put our SKUs + RUO attestation flag there |
| Webhooks | `webhooks.create({storeId, url, eventTypes, description})` → `{id, secret}`; header `X-TagadaPay-Signature: sha256=<hex>` = HMAC-SHA256(secret, raw body); also `X-TagadaPay-Timestamp`, `-Event-Type`, `-Event-Id`, `-Delivery-Attempt`; 10 s timeout, 6 retries over ~24 h, dedupe on event `id`, endpoint auto-disabled after 3 days of failures | Receiver at `https://energypeptides.us/api/webhooks/kashu`; secret in `TAGADA_WEBHOOK_SECRET`; verify then 200 fast; dedupe by event id; `order/paid` → ledger `sold` events per line item (needs `orders.retrieve(orderId)` for line items — sample payload carries only orderId, totalAmount, currency, customerEmail) |
| Events to subscribe | `order/paid`, `order/refunded`, `payment/failed`, `order/failed` | refunds → `released`/`adjusted` events; failures → log only |
| Sandbox | processor `type: 'sandbox'`, `options.testMode: true`; any card approved; 3DS skipped; webhooks fire | Full end-to-end rehearsal before go-live |
| Rate limits | 100 req/min standard | Irrelevant at our size; sync batches anyway |

## Open questions for the Kashu dashboard (names only, never values)
1. Does Settings show **API Keys / Access Tokens**, and a **Store ID**?
2. Is the API host `api.tagada.io` or a Kashu-branded host?
3. Is a sandbox processor available on the Kashu account, or only live?
4. Has a checkout route / funnel been published (`checkoutRoutePublished`)?

## Doc pages used
- https://docs.tagada.io/llms.txt (index)
- https://docs.tagada.io/api-reference/introduction
- https://docs.tagada.io/developer-tools/node-sdk/quick-start
- https://docs.tagada.io/developer-tools/node-sdk/checkout-sessions
- https://docs.tagada.io/developer-tools/node-sdk/webhooks-events
- https://docs.tagada.io/api-reference/products/create-product
- https://docs.tagada.io/developer-tools/node-sdk/sandbox-testing
- https://docs.tagada.io/developer-tools/headless-sdk/introduction

---
# Kashu dashboard developer docs (pasted by Jett 2026-09-09) — what changed vs the public docs

**Base URL is Kashu-specific:** `https://api.tagadapay.io` (SDK `baseUrl`), with `/api/public/v1` (CRM: stores,
orders, payments) and `/api/tagadapay/v1` (processing: TPAs, KYB, keys). Not `api.tagada.io`.

**Keys:** `Authorization: Bearer tp_sk_…`. Partner keys (`tp_sk_partner_*`) belong to Kashu, not us. What a
merchant needs is a **TPA-restricted processing key** (`tp_sk_test_…` / `tp_sk_live_…`) minted for our TPA, plus
our **storeId** (`store_…`, auto-provisioned with the TPA; `stores.list({accountId})`). Test keys → sandbox
(any card approved, 3DS skipped). Secrets are shown once; they live only in Cloudflare env / local `.env`.

**Two payment paths offered:**
- **Path A — direct S2S (chosen).** No checkout session, no products/cart/orders in Tagada. Browser tokenises the
  card with `@tagadapay/core-js` (`new TagadaCore({environment}).tokenizeCard({cardNumber, expiryDate, cvc,
  cardholderName})` → `{tagadaToken, rawToken}`; `rawToken.metadata.auth.scaRequired` hints 3DS). Server (Cloudflare
  Function, processing key):
  1. `paymentInstruments.createFromToken({tagadaToken, storeId, customerData:{email, firstName, lastName}})` → `{paymentInstrument, customer}`
  2. optional `threeds.createSession({provider:'basis_theory', storeId, paymentInstrumentId, sessionData})`
  3. `payments.process({paymentInstrumentId, customerId, storeId, amount (cents), currency:'USD', paymentMethod:'card', mode:'purchase', threedsSessionId?, returnUrl})`
     → `payment.requireAction === 'redirect'` ⇒ send `requireActionData.redirectUrl` to the client and resume on `/3ds/return`; else final status.
  Raw endpoints: `POST /api/public/v1/payment-instruments/create-from-token`, `/threeds/create-session`, `/payments/process`.
  PAN never touches our server (BasisTheory tokenizer) — we stay out of PCI scope.
- **Path B — headless SDK.** Needs a Tagada checkout session and products in Tagada. Not chosen (duplicates the catalog).

**Consequences for the graph:** the graph is the only catalog; `kg sync` is NOT needed for Kashu (kept for future
channels). Orders need our own record (SQLite/D1 table beside the graph, no PII in the graph). A successful
`payments.process` writes ledger `sold` events synchronously; webhooks reconcile refunds/disputes.

**Webhooks — two envelope styles exist, receiver must accept both:**
- Partner/dashboard style: header `tagadapay-signature`; envelope `{object:'event', id:'evt_…', accountId:'tpa_…',
  type:'payout.paid' (dot format), created: unix seconds, apiVersion, livemode, data:{object:{…}}}`;
  SDK `tagadapay.webhooks.constructEvent(rawBody, signatureHeader, secret)` verifies + parses (throws on bad sig).
  Retries 1m, 5m, 30m, 2h, 6h, 12h; 2xx within 10 s acks; dedupe on event id.
- Public-docs style: header `X-TagadaPay-Signature: sha256=<hex>` (HMAC-SHA256 of raw body), slash-format types
  (`order/paid`, `payment/succeeded`, `payment/refunded`).
- Events we care about: `payment.succeeded`/`payment/succeeded` (reconcile), `payment/refunded`, `dispute.created`,
  `payout.paid` (bookkeeping only). Endpoint: `https://energypeptides.us/api/webhooks/kashu`, secret `TAGADA_WEBHOOK_SECRET`.

**Payment methods:** card (Visa/MC/Amex), apple_pay, google_pay via core-js tokenisation example; APMs are EU-only.
`paymentSetup.get(storeId)` tells us what the account has enabled — check before rendering wallet buttons.

**Errors:** JSON `{error:{code, message}}`; codes invalid_request, missing_api_key, invalid_api_key, forbidden_scope,
tpa_access_denied, account_not_found, account_create_failed.

**Env vars (Cloudflare Pages project + local .env, never in repo):**
`TAGADA_API_KEY` (processing key, test then live), `TAGADA_STORE_ID`, `TAGADA_WEBHOOK_SECRET`, `TAGADA_ENV` (test|live).

---
# Live findings with the real key (2026-09-10)

- Kashu issued an **admin key with prefix `sk_crm_`** (not a `tp_sk_*` processing key). It is accepted on the public API at
  **`https://api.tagada.io/api/public/v1`** (also `app.tagadapay.com`). `api.tagadapay.io` only serves the partner routes
  and 404s for `/api/public/v1/*` — Kashu's pasted docs were partner-facing. Base URL corrected everywhere.
- Store: `store_bfac3259d86e` ("Energy peptides", USD, type tagadapay), account `acc_abe5f06b8e8a`, created 2026-07-28.
- `GET /stores/{id}/payment-setup` → `config: {}`; `GET /processors` → `[]`; `GET /payment-flows` → `[]`.
  **No processor or payment flow is attached — charges are impossible (test or live) until one is.**
- `GET /webhooks?storeId=…` → Kashu's own endpoint `whe_10a780d8b5b0` → `https://mrp.kashupay.com/api/webhooks/tagada-store`
  for `payment/succeeded|refunded|failed` (their reconciliation). Our endpoint is added separately when deployed.
- Endpoints that 404 on this host with this key: `/auth/test`, `/orders`, `/products`, `/payment-setup?storeId=`.
  `/processors` and `/webhooks` require `storeId` as a query param (Zod-validated).

## Sandbox wiring (done 2026-09-10, with Jett's approval)
- Create routes are `POST …/processors/create`, `POST …/payment-flows/create`, `POST …/stores/create` (plain POST on the
  collection 404s). There is NO store update endpoint (PATCH 405 / PUT 404), so a flow cannot be attached to the
  Kashu-provisioned store after the fact; `payments/process` accepts an explicit `paymentFlowId` instead.
- Sandbox processor `processor_e7eafa6c3033` (type sandbox, testMode) → payment flow `flow_f31f6606f6b5` (simple,
  weighted 100%) → **sandbox store `store_853bff37b991`** "Energy Peptides — SANDBOX (integration testing)", created
  with `selectedPaymentFlowId`. Local `.dev.vars` points at the sandbox store; live store stays `store_bfac3259d86e`.
- `payments/process` schema: required amount (cents), currency, storeId; optional orderId, paymentInstrumentId,
  customerId, mode, paymentMethod, processorId, paymentFlowId, threedsSessionId, returnUrl, initiatedBy,
  shippingAddress/billingAddress (recommended). No `metadata` field. Response `payment.{id,status,subStatus,requireAction}`.
- Card tokens must come from the PRODUCTION tokenizer tenant (`PUBLIC_TOKENIZER_ENV=production`) even for the sandbox
  processor, which lives on the production API.
- Going live: either Kashu attaches a live processor/flow to `store_bfac3259d86e`, or we set `TAGADA_PAYMENT_FLOW_ID`
  to a live flow on our side. Then delete/archive the sandbox processor, flow and store.
- **First sandbox purchase succeeded 2026-09-10** (order EP-MTUVE78C-240CAF0B, $68.95, card 4242…). Three adapter fixes
  found on the way: (1) the 3DS pre-session must be best-effort — the production tokenizer flags SCA and a flow with
  3DS disabled rejects the session; (2) never send our order reference as `orderId` (it is Tagada's order id →
  "Order not found"); (3) no `metadata` field. Link orders by the returned `payment.id`.

## Deployment (2026-09-10)
- Cloudflare account: the one wrangler is logged into (seanmccully2@gmail.com, confirmed by Jett as his). Worker `energy-peptides`,
  D1 `energy-peptides-orders` (id 65d0803d-9ddc-46ff-b137-f7bc3363f4e6), schema applied remotely.
- Secrets set via `wrangler secret put`: TAGADA_API_KEY, TAGADA_STORE_ID (sandbox store), TAGADA_WEBHOOK_SECRET.
- Vars: PAYMENT_MODE=tagada, TAGADA_ENV=test, TAGADA_BASE_URL=https://api.tagada.io.
- Route: custom domain **https://preview.energypeptides.us** (no workers.dev subdomain on the account; dashboard offered
  only "add domain / add route"). Launch = swap route to energypeptides.us (+ www) in wrangler.jsonc.
- Our webhook on the sandbox store: `whe_0eb013b66ba3` → https://preview.energypeptides.us/api/webhooks/kashu
  (payment/succeeded|failed|refunded, order/paid|refunded). Re-register on the live store at launch.

## Catalog mirror + live webhook (2026-09-10)
- Product routes (public API, api.tagada.io): `POST /products/create` {storeId, name, description, active, isShippable,
  isTaxable, unitLabel, variants:[{name, sku, active, default, prices:[{currencyOptions:{USD:{amount: cents}}}]}]};
  `POST /products/list` {storeId, page, per_page, includeVariants}; `PUT /products/{id}` {updatedData:{name, description,
  active, ...}} (no variants — prices cannot be edited); `POST /products/delete` {productIds}. `inStock` is ignored on create.
- `kg sync --adapter kashu` (kg/sync.py KashuAdapter): one product per SKU, active = graph active AND on hand > 0,
  price change = delete + recreate. Checkout never references these ids. Target store `TAGADA_CATALOG_STORE_ID`
  (live store). 21 products created 2026-09-10; ids in seeds/14_platform_ids.yaml. Only SKUs starting `EP-` are touched.
- Webhook create route is `POST /webhooks` (NOT /webhooks/create). Live store webhook `whe_e81e80754f44` →
  https://energypeptides.us/api/webhooks/kashu (starts receiving once the root domain is attached). TAGADA_WEBHOOK_SECRET
  holds both secrets comma-separated (sandbox, live); receiver accepts either.
- Kashu also auto-attached its own reconciliation webhook to the sandbox store (whe_656634f417e7 → mrp.kashupay.com),
  so sandbox test payments are visible to Kashu.
- Cloudflare bot protection returns 403 to Python-urllib user agents on the site; Tagada's deliveries and curl pass.
