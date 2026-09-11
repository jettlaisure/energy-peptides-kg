# Energy Peptides — AI infrastructure (knowledge graph + task graphs)

This repo is the company's memory and its playbook. Read this file, then use the skills; do not read
`seeds/` wholesale or `data/graph.db` directly. Progressive disclosure: `kg index` → `kg card` →
`kg context <recipe>`. Load only what the task needs.

## Commands (run with `uv run`)
- `kg rebuild` — rebuild the DB from `seeds/` (derived; always safe)
- `kg index` / `kg card "<Type:Name>"` / `kg context <recipe> "<Type:Name>"` / `kg recipes`
- `kg stock [product] [--events]` / `kg gaps` / `kg path A B` / `kg query <Type> --attr value`
- `kg validate` — graph vs ontology (run after every ingest; must be clean)
- `kg fuse` / `kg extract <file>` / `kg staging …` — dedup and LLM extraction (see README)
- `kg sync plan|apply --adapter kashu` — mirror the catalog (21 SKUs, prices, in/out of stock) into the live Kashu store.
  Run after any price, status or stock change. One Kashu product per SKU; price changes recreate that product.

- `kg map` — visual map for humans at `data/graph-map.html` (auto-refreshed on ingest). Never read it, `kg/vendor/`
  or `data/graph.db` into context (denied in `.claude/settings.json`); agents use index/card/context instead.

## Website (`web/`, Astro + Cloudflare)
- Renders from `kg export --format site` (catalog.json). Never hand-edit product data in `web/`; change seeds.
- `cd web && npm run preview` for a local build on :8788 (test-mode checkout). See `web/README.md` for deploy.
- Orders live in Cloudflare D1, not the graph. `kg orders pull [--remote] --apply` writes `sold` ledger events.
- Brand: `inbox/brand.html` is the authoritative Brand Reference v1.0; tokens in `web/src/styles/tokens.css`, rules in
  `seeds/09_brand.yaml`. Dark-ground navy + gold, Satoshi only, browse by composition class, never by use or goal.
  Compliance line verbatim, either of two approved lines: 'For Research Use Only — Not for Human Consumption' (site)
  or 'For Research Use Only - Not for Human Use' (labels). Label nicknames (KLOW) only with components + amounts.
  Certificates are not published: 'tested to ≥99%, certificates on request'. Copy comes from Claims/FAQs.

## Skills (each executes a task graph in `taskgraphs/`)
`/new-product-page`, `/faq-seo-addition`, `/marketing-copy`, `/inventory`, `/kg-query`.

## Non-negotiables
- Schema is `ontology.yaml`. Add types/relations only when `competency_questions.md` needs them.
- Knowledge changes go through `seeds/*.yaml` → `kg ingest` → `kg validate`. Never write the DB by hand.
- Every fact keeps `source` and `confidence`. conf medium/low = unverified: say so, never publish as fact.
- Cite only Study nodes with `verified: true`. Only `status: approved` Claims go into copy.
- Publishing, sending, deploying and stock write-downs pass a human gate. Drafts are `*.draft.md`.
- Seed chemistry, citations, compliance and brand rules were model-drafted on 2026-09-08 and are
  flagged medium confidence until a human verifies them and edits the seed file.
