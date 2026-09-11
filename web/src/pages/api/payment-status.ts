export const prerender = false;
import type { APIRoute } from 'astro';
import { getEnv } from '../../server/env';
import { paymentAdapter } from '../../server/payments';
import { getOrder, setOrderPayment } from '../../server/orders';

export const GET: APIRoute = async ({ url }) => {
  const env = getEnv();
  const id = url.searchParams.get('order') ?? '';
  const order = await getOrder(env.DB, id);
  if (!order) return new Response(JSON.stringify({ status: 'error' }), { status: 404, headers: { 'content-type': 'application/json' } });
  let status = order.status;
  if (status === 'requires_action' && order.payment_id) {
    const s = await paymentAdapter(env).status(order.payment_id).catch(() => 'pending' as const);
    if (s !== 'pending') { status = s; await setOrderPayment(env.DB, id, s, order.payment_id); }
  }
  return new Response(JSON.stringify({ status: status === 'requires_action' ? 'pending' : status }), { headers: { 'content-type': 'application/json' } });
};
