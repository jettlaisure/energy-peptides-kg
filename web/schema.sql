-- Orders live here (Cloudflare D1), never in the knowledge graph. No card data is ever stored.
CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,                -- ep_<ulid-ish>
  created_at TEXT NOT NULL,
  status TEXT NOT NULL,               -- pending | requires_action | paid | failed | refunded | canceled
  email TEXT NOT NULL,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  shipping_json TEXT NOT NULL,        -- address as JSON
  subtotal_cents INTEGER NOT NULL,
  shipping_cents INTEGER NOT NULL,
  total_cents INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  attestation_at TEXT NOT NULL,       -- when the 21+ / research-use attestation was accepted
  payment_mode TEXT NOT NULL,         -- stub | tagada
  payment_id TEXT,                    -- Tagada payment id
  customer_id TEXT,                   -- Tagada customer id
  last_error TEXT,
  ledger_synced_at TEXT               -- set once `kg orders pull` has written the sold events
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_payment ON orders(payment_id);
CREATE TABLE IF NOT EXISTS order_items (
  order_id TEXT NOT NULL REFERENCES orders(id),
  sku TEXT NOT NULL,
  name TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  unit_cents INTEGER NOT NULL,
  PRIMARY KEY (order_id, sku)
);
CREATE TABLE IF NOT EXISTS webhook_events (
  id TEXT PRIMARY KEY,                -- event id from Kashu/Tagada (dedupe)
  type TEXT NOT NULL,
  received_at TEXT NOT NULL,
  payload TEXT NOT NULL
);
