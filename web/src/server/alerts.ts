/* Owner alerts for paid orders. One message per paid order, whichever path confirmed it (checkout,
   payment-status poll or Kashu webhook); D1 table order_alerts dedupes. Lines on a just-in-time SKU
   with no stock on hand are flagged as a Monārch pickup, so an order becomes a trip without watching
   a dashboard. Channels, all optional, set with `wrangler secret put`:
     ALERT_SLACK_WEBHOOK_URL     Slack incoming webhook (posts to the channel the webhook was created for)
     ALERT_NTFY_TOPIC            push to phone via ntfy.sh (subscribe to the same topic in the ntfy app)
     RESEND_API_KEY + ALERT_EMAIL_TO [+ ALERT_EMAIL_FROM]   email via Resend
   With none set the alert is only logged. Never throws: an alert failure must not fail an order.
   No customer name or email leaves D1; the message carries order id, lines and city/state/zip. */
import type { Env } from './env';
import { productsBySku, catalog } from '../lib/catalog';
import { orderLines, orderSummary, recordAlert, soldSince } from './orders';

export interface AlertLine { sku: string; name: string; quantity: number; pickup: boolean; shortfall: number }

/* A line needs a pickup when the SKU is just-in-time and units sold since the catalog was built
   (this order included) exceed what the graph says is on hand. */
export async function classifyLines(db: D1Database, orderId: string): Promise<AlertLine[]> {
  const out: AlertLine[] = [];
  for (const l of await orderLines(db, orderId)) {
    const p = productsBySku.get(l.sku);
    let pickup = false, shortfall = 0;
    if (p && p.fulfilment === 'just_in_time') {
      const sold = await soldSince(db, l.sku, catalog.generated_at);
      shortfall = Math.max(0, sold - Number(p.on_hand ?? 0));
      pickup = shortfall > 0;
    }
    out.push({ sku: l.sku, name: l.name, quantity: l.quantity, pickup, shortfall });
  }
  return out;
}

export async function alertOrderPaid(env: Env, orderId: string): Promise<void> {
  try {
    if (!(await recordAlert(env.DB, orderId, 'paid'))) return;      // already sent for this order
    const o = await orderSummary(env.DB, orderId);
    if (!o) return;
    const lines = await classifyLines(env.DB, orderId);
    const pickups = lines.filter((l) => l.pickup);
    const vials = lines.reduce((n, l) => n + l.quantity, 0);
    let ship: Record<string, string> = {};
    try { ship = JSON.parse(o.shipping_json); } catch { /* keep empty */ }
    const title = pickups.length
      ? `Pickup needed: ${pickups.map((l) => l.name).join(', ')} · order ${orderId}`
      : `Order ${orderId} paid · ship ${vials} vial${vials === 1 ? '' : 's'}`;
    const body = [
      `Order ${orderId} · $${(o.total_cents / 100).toFixed(2)} · ${o.created_at.replace('T', ' ').slice(0, 16)} UTC`,
      ...pickups.map((l) => `PICKUP (just-in-time, ${l.shortfall} short): ${l.name} ×${l.quantity} → buy a kit at Monārch, record the lot with /inventory, then ship`),
      ...lines.filter((l) => !l.pickup).map((l) => `Ship from stock: ${l.name} ×${l.quantity}`),
      `Ship to: ${[ship.city, ship.state, ship.postalCode].filter(Boolean).join(' ')}`,
    ].join('\n');
    const sent = await Promise.all([sendSlack(env, title, body, pickups.length > 0), sendNtfy(env, title, body, pickups.length > 0), sendEmail(env, title, body)]);
    if (!sent.some(Boolean)) console.log(`[alert] no channel configured\n${title}\n${body}`);
  } catch (e) {
    console.error('[alert] failed', orderId, e);
  }
}

async function sendSlack(env: Env, title: string, body: string, urgent: boolean): Promise<boolean> {
  if (!env.ALERT_SLACK_WEBHOOK_URL) return false;
  const res = await fetch(env.ALERT_SLACK_WEBHOOK_URL, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ text: `${urgent ? ':rotating_light: ' : ':package: '}*${title}*\n${body}` }),
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) console.error('[alert] slack', res.status, await res.text().catch(() => ''));
  return res.ok;
}

async function sendNtfy(env: Env, title: string, body: string, urgent: boolean): Promise<boolean> {
  if (!env.ALERT_NTFY_TOPIC) return false;
  const res = await fetch(`https://ntfy.sh/${encodeURIComponent(env.ALERT_NTFY_TOPIC)}`, {
    method: 'POST', body,
    headers: { Title: title, Priority: urgent ? 'high' : 'default', Tags: urgent ? 'car,package' : 'package' },
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) console.error('[alert] ntfy', res.status, await res.text().catch(() => ''));
  return res.ok;
}

async function sendEmail(env: Env, subject: string, text: string): Promise<boolean> {
  if (!env.RESEND_API_KEY || !env.ALERT_EMAIL_TO) return false;
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { authorization: `Bearer ${env.RESEND_API_KEY}`, 'content-type': 'application/json' },
    body: JSON.stringify({ from: env.ALERT_EMAIL_FROM ?? 'Energy Peptides <alerts@energypeptides.us>', to: env.ALERT_EMAIL_TO.split(',').map((s) => s.trim()), subject, text }),
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) console.error('[alert] resend', res.status, await res.text().catch(() => ''));
  return res.ok;
}
