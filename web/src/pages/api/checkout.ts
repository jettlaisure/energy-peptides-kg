export const prerender = false;
import type { APIRoute } from 'astro';
import { productsBySku, cents, shippingCents, catalog } from '../../lib/catalog';
import { getEnv } from '../../server/env';
import { paymentAdapter } from '../../server/payments';
import { createOrder, newOrderId, setOrderPayment, soldSince } from '../../server/orders';

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json' } });
const email = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const POST: APIRoute = async ({ request, url }) => {
  let body: any;
  try { body = await request.json(); } catch { return json({ error: 'Invalid request.' }, 400); }
  const env = getEnv();

  // ---- validate (never trust client prices) ----
  const items: { sku: string; qty: number }[] = Array.isArray(body?.items) ? body.items : [];
  if (items.length === 0) return json({ error: 'Your cart is empty.' }, 400);
  if (body?.attestation !== true) return json({ error: 'The research-use attestation is required.' }, 400);
  const c = body?.customer ?? {}, s = body?.shipping ?? {};
  for (const [k, v] of Object.entries({ email: c.email, firstName: c.firstName, lastName: c.lastName, line1: s.line1, city: s.city, state: s.state, postalCode: s.postalCode }))
    if (typeof v !== 'string' || !v.trim()) return json({ error: `Missing ${k}.` }, 400);
  if (!email.test(c.email)) return json({ error: 'Enter a valid email address.' }, 400);
  if (s.country && s.country !== 'US') return json({ error: 'We ship within the United States only.' }, 400);

  const lines = [];
  let subtotal = 0;
  for (const it of items) {
    const p = productsBySku.get(String(it.sku));
    const qty = Number(it.qty);
    if (!p || !Number.isInteger(qty) || qty < 1 || qty > 20) return json({ error: 'A cart line is invalid.' }, 400);
    if (!(p.in_stock && p.status === 'active')) return json({ error: `${p.name} is not available.` }, 409);
    const sold = await soldSince(env.DB, p.sku, catalog.generated_at);
    if (p.on_hand - sold < qty) return json({ error: `Only ${Math.max(0, p.on_hand - sold)} of ${p.name} remain.` }, 409);
    const unit = cents(p.price_usd);
    lines.push({ sku: p.sku, name: p.name, quantity: qty, unitCents: unit });
    subtotal += unit * qty;
  }
  const ship = shippingCents(subtotal);
  const total = subtotal + ship;

  // ---- record, then charge ----
  const orderId = newOrderId();
  const adapter = paymentAdapter(env);
  await createOrder(env.DB, {
    id: orderId, email: c.email.trim().toLowerCase(), firstName: c.firstName.trim(), lastName: c.lastName.trim(),
    shipping: { organization: s.organization ?? '', line1: s.line1, line2: s.line2 ?? '', city: s.city, state: s.state, postalCode: s.postalCode, country: 'US', phone: c.phone ?? '' },
    items: lines, subtotalCents: subtotal, shippingCents: ship, totalCents: total, paymentMode: adapter.mode,
  });
  const result = await adapter.charge({
    orderId, amountCents: total, currency: 'USD', tagadaToken: String(body.tagadaToken ?? ''), scaRequired: Boolean(body.scaRequired),
    customer: { email: c.email, firstName: c.firstName, lastName: c.lastName, phone: c.phone },
    returnUrl: `${url.origin}/checkout/return/?order=${encodeURIComponent(orderId)}`,
    address: { line1: s.line1, line2: s.line2 ?? '', city: s.city, state: s.state, postalCode: s.postalCode, country: 'US' },
    metadata: { orderId, skus: lines.map((l) => `${l.sku}x${l.quantity}`).join(','), ruo_attested: 'true' },
  });
  if (result.status === 'failed') {
    await setOrderPayment(env.DB, orderId, 'failed', result.paymentId, undefined, result.error);
    return json({ status: 'failed', orderId, error: 'The payment was not approved. No charge was made.' }, 402);
  }
  await setOrderPayment(env.DB, orderId, result.status, result.paymentId, result.customerId);
  return json(result.status === 'paid' ? { status: 'paid', orderId } : { status: 'requires_action', orderId, redirectUrl: result.redirectUrl });
};
