export const prerender = false;
import type { APIRoute } from 'astro';
import { getEnv } from '../../../server/env';
import { verifySignature, normalizeEvent } from '../../../server/webhook';
import { recordWebhookEvent, setStatusByPayment, setOrderPayment } from '../../../server/orders';

/* Kashu / Tagada events. Verify, dedupe, ack fast. Refunds and disputes are reconciled here;
   successful payments are usually already recorded synchronously by /api/checkout. */
export const POST: APIRoute = async ({ request }) => {
  const env = getEnv();
  const raw = await request.text();
  if (!env.TAGADA_WEBHOOK_SECRET) return new Response('webhook secret not configured', { status: 503 });
  if (!(await verifySignature(raw, request.headers, env.TAGADA_WEBHOOK_SECRET))) return new Response('invalid signature', { status: 401 });
  let payload: any;
  try { payload = JSON.parse(raw); } catch { return new Response('bad json', { status: 400 }); }
  const ev = normalizeEvent(payload);
  if (!ev.id) return new Response('missing event id', { status: 400 });
  const fresh = await recordWebhookEvent(env.DB, ev.id, ev.type, raw);
  if (!fresh) return new Response('duplicate', { status: 200 });

  const statusFor: Record<string, string> = {
    'payment.succeeded': 'paid', 'order.paid': 'paid', 'payment.authorized': 'paid',
    'payment.failed': 'failed', 'payment.rejected': 'failed', 'order.failed': 'failed',
    'payment.refunded': 'refunded', 'order.refunded': 'refunded',
  };
  const next = statusFor[ev.type];
  if (next) {
    if (ev.orderId) await setOrderPayment(env.DB, ev.orderId, next, ev.paymentId);
    else if (ev.paymentId) await setStatusByPayment(env.DB, ev.paymentId, next);
  }
  return new Response('ok', { status: 200 });
};
