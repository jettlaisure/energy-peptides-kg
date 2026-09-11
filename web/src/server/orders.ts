/* Orders in Cloudflare D1. PII lives here and in Kashu, never in the knowledge graph. */
export interface NewOrder {
  id: string; email: string; firstName: string; lastName: string; shipping: Record<string, string>;
  items: { sku: string; name: string; quantity: number; unitCents: number }[];
  subtotalCents: number; shippingCents: number; totalCents: number; paymentMode: string;
}
export function newOrderId(): string {
  const t = Date.now().toString(36).toUpperCase();
  const r = crypto.getRandomValues(new Uint8Array(4)).reduce((s, b) => s + b.toString(16).padStart(2, '0'), '').toUpperCase();
  return `EP-${t}-${r}`;
}
export async function createOrder(db: D1Database, o: NewOrder): Promise<void> {
  const now = new Date().toISOString();
  const stmts = [
    db.prepare(`INSERT INTO orders (id, created_at, status, email, first_name, last_name, shipping_json, subtotal_cents, shipping_cents, total_cents, currency, attestation_at, payment_mode)
                VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?)`)
      .bind(o.id, now, o.email, o.firstName, o.lastName, JSON.stringify(o.shipping), o.subtotalCents, o.shippingCents, o.totalCents, now, o.paymentMode),
    ...o.items.map((it) => db.prepare(`INSERT INTO order_items (order_id, sku, name, quantity, unit_cents) VALUES (?, ?, ?, ?, ?)`).bind(o.id, it.sku, it.name, it.quantity, it.unitCents)),
  ];
  await db.batch(stmts);
}
export async function setOrderPayment(db: D1Database, id: string, status: string, paymentId?: string, customerId?: string, error?: string): Promise<void> {
  await db.prepare(`UPDATE orders SET status = ?, payment_id = COALESCE(?, payment_id), customer_id = COALESCE(?, customer_id), last_error = ? WHERE id = ?`)
    .bind(status, paymentId ?? null, customerId ?? null, error ?? null, id).run();
}
export async function setStatusByPayment(db: D1Database, paymentId: string, status: string): Promise<number> {
  const r = await db.prepare(`UPDATE orders SET status = ? WHERE payment_id = ?`).bind(status, paymentId).run();
  return r.meta.changes ?? 0;
}
export async function getOrder(db: D1Database, id: string) {
  return db.prepare(`SELECT id, status, payment_id, total_cents FROM orders WHERE id = ?`).bind(id).first<{ id: string; status: string; payment_id: string | null; total_cents: number }>();
}
/* Units sold since the catalog was generated, per SKU — guards against overselling between site builds. */
export async function soldSince(db: D1Database, sku: string, sinceIso: string): Promise<number> {
  const r = await db.prepare(`SELECT COALESCE(SUM(oi.quantity), 0) AS n FROM order_items oi JOIN orders o ON o.id = oi.order_id
                              WHERE oi.sku = ? AND o.created_at >= ? AND o.status IN ('pending', 'requires_action', 'paid')`).bind(sku, sinceIso).first<{ n: number }>();
  return Number(r?.n ?? 0);
}
export async function recordWebhookEvent(db: D1Database, id: string, type: string, payload: string): Promise<boolean> {
  const r = await db.prepare(`INSERT OR IGNORE INTO webhook_events (id, type, received_at, payload) VALUES (?, ?, ?, ?)`).bind(id, type, new Date().toISOString(), payload).run();
  return (r.meta.changes ?? 0) > 0;   // false = duplicate delivery
}
