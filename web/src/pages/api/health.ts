export const prerender = false;
import type { APIRoute } from 'astro';
import { getEnv } from '../../server/env';
import { catalog } from '../../lib/catalog';
export const GET: APIRoute = async () => {
  const env = getEnv();
  const db = await env.DB.prepare('SELECT COUNT(*) AS n FROM orders').first<{ n: number }>().then((r) => ({ ok: true, orders: r?.n ?? 0 })).catch((e) => ({ ok: false, error: String(e) }));
  return new Response(JSON.stringify({ ok: true, payment_mode: env.PAYMENT_MODE ?? 'stub', catalog_generated_at: catalog.generated_at, products: catalog.products.length, db }), { headers: { 'content-type': 'application/json' } });
};
