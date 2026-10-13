export const prerender = false;
import type { APIRoute } from 'astro';
import { getEnv } from '../../../server/env';
import { issueCode } from '../../../server/membership';

const json = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/* Email a 6-digit code. Same answer whether or not the address has ordered before. */
export const POST: APIRoute = async ({ request }) => {
  const env = getEnv();
  const body = await request.json().catch(() => ({}));
  const email = String(body?.email ?? '').trim().toLowerCase();
  if (!emailRe.test(email)) return json({ error: 'Enter a valid email address.' }, 400);
  const r = await issueCode(env, email);
  if (!r.ok) return json({ error: r.error }, 429);
  return json({ sent: true, ...(r.devCode ? { devCode: r.devCode } : {}) });
};
