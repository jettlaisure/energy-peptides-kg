export const prerender = false;
import type { APIRoute } from 'astro';
import { getEnv } from '../../../server/env';
import { COOKIE, checkCode } from '../../../server/membership';

const json = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });

/* Check the code; on success remember this device for that email (HttpOnly cookie, 90 days). */
export const POST: APIRoute = async ({ request, cookies, url }) => {
  const env = getEnv();
  const body = await request.json().catch(() => ({}));
  const r = await checkCode(env.DB, String(body?.email ?? ''), String(body?.code ?? ''));
  if (!r.ok) return json({ error: r.error }, 400);
  cookies.set(COOKIE, r.token!, { path: '/', httpOnly: true, sameSite: 'lax', secure: url.protocol === 'https:', maxAge: r.maxAge });
  return json({ verified: true });
};
