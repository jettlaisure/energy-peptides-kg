export const prerender = false;
import type { APIRoute } from 'astro';
import { getEnv } from '../../../server/env';
import { COOKIE, LEVELS, statusFor, verifiedEmail } from '../../../server/membership';
import { progressLine } from '../../../lib/membership-rules';

const json = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });

/* Status for the email typed at checkout. Revealed only when this device is verified for that email; otherwise the
   answer is the same for every address, so nobody learns whether an email has ordered before. */
export const POST: APIRoute = async ({ request, cookies }) => {
  const env = getEnv();
  const body = await request.json().catch(() => ({}));
  const email = String(body?.email ?? '').trim().toLowerCase();
  const cartNet = Math.max(0, Number(body?.cartCents ?? 0));
  const levels = LEVELS.map((l) => ({ name: l.name, min_usd: l.min_usd, discount_pct: l.discount_pct, free_shipping: l.free_shipping }));
  const verified = email && (await verifiedEmail(env.DB, cookies.get(COOKIE)?.value)) === email;
  const canVerify = Boolean(env.RESEND_API_KEY) || (env.PAYMENT_MODE ?? 'stub') === 'stub';
  if (!verified) return json({ verified: false, levels, canVerify });
  const s = await statusFor(env.DB, email);
  const l = LEVELS[s.level];
  const net = cartNet - Math.round((cartNet * l.discount_pct) / 100);
  return json({ verified: true, levels, level: s.name, discountPct: l.discount_pct, freeShipping: l.free_shipping,
                holdsUntil: s.holdsUntil, line: progressLine(LEVELS, s, net) });
};
