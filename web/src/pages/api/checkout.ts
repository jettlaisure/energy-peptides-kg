export const prerender = false;
import type { APIRoute } from 'astro';
import { productsBySku, cents, shippingCents, catalog } from '../../lib/catalog';
import { getEnv } from '../../server/env';
import { paymentAdapter } from '../../server/payments';
import { createOrder, newOrderId, setOrderPayment, soldSince } from '../../server/orders';
import { orderingOpen } from '../../server/ordering';
import { alertOrderPaid } from '../../server/alerts';
import { COOKIE, LEVELS, statusFor, verifiedEmail } from '../../server/membership';
import { price } from '../../lib/membership-rules';

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json' } });
const email = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const POST: APIRoute = async ({ request, url, cookies }) => {
  const env = getEnv();
  // Checked before anything else: a sandbox processor approves every card and charges nothing, so
  // until the live store is attached no order may be recorded, whatever a stale page posts here.
  if (!orderingOpen(env)) return json({ error: 'Ordering is not open yet.' }, 503);

  let body: any;
  try { body = await request.json(); } catch { return json({ error: 'Invalid request.' }, 400); }

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
    const avail = p.fulfilment === 'just_in_time' ? Math.max(p.on_hand, 10) : p.on_hand;   // JIT: one kit is collected on order
    if (avail - sold < qty) return json({ error: `Only ${Math.max(0, avail - sold)} of ${p.name} remain.` }, 409);
    const unit = cents(p.price_usd);
    lines.push({ sku: p.sku, name: p.name, quantity: qty, unitCents: unit });
    subtotal += unit * qty;
  }
  // Member pricing only when this device is verified for the checkout email (see server/membership.ts).
  const buyer = c.email.trim().toLowerCase();
  const member = (await verifiedEmail(env.DB, cookies.get(COOKIE)?.value)) === buyer ? await statusFor(env.DB, buyer) : null;
  const level = member?.level ?? 0;
  const { discount, shipping: ship, total } = price(LEVELS, level, subtotal, shippingCents);

  // ---- record, then charge ----
  const orderId = newOrderId();
  const adapter = paymentAdapter(env);
  await createOrder(env.DB, {
    id: orderId, email: c.email.trim().toLowerCase(), firstName: c.firstName.trim(), lastName: c.lastName.trim(),
    shipping: { organization: s.organization ?? '', line1: s.line1, line2: s.line2 ?? '', city: s.city, state: s.state, postalCode: s.postalCode, country: 'US', phone: c.phone ?? '' },
    items: lines, subtotalCents: subtotal, shippingCents: ship, totalCents: total, paymentMode: adapter.mode,
    discountCents: discount, memberLevel: LEVELS[level].name,
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
  if (result.status === 'paid') await alertOrderPaid(env, orderId);   // owner alert: ship, or just-in-time pickup
  return json(result.status === 'paid' ? { status: 'paid', orderId } : { status: 'requires_action', orderId, redirectUrl: result.redirectUrl });
};
