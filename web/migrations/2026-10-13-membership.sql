-- One-time migration for databases created before membership status (2026-10-13). New databases get this from schema.sql.
-- Run once: npx wrangler d1 execute energy-peptides-orders --remote --file=./migrations/2026-10-13-membership.sql
ALTER TABLE orders ADD COLUMN discount_cents INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN member_level TEXT;
CREATE INDEX IF NOT EXISTS idx_orders_email ON orders(email);
CREATE TABLE IF NOT EXISTS member_codes (
  email TEXT PRIMARY KEY, code_hash TEXT NOT NULL, expires_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, sends INTEGER NOT NULL DEFAULT 0, window_start TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS member_devices (
  token_hash TEXT PRIMARY KEY, email TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
