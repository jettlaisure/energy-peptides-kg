/* Membership status on the server: order history from D1, emailed one-time codes, remembered devices.
   Status is never revealed for an email until that email is verified on this device, so typing someone else's
   address shows nothing and unlocks nothing. Rules live in ../lib/membership-rules.ts; levels in site.yaml. */
import type { Env } from './env';
import { catalog } from '../lib/catalog';
import { statusAt, type Level, type PaidOrder, type Status } from '../lib/membership-rules';

export const LEVELS: Level[] = (catalog.site as any).membership?.levels ?? [{ name: 'Navy', min_usd: 0, discount_pct: 0, free_shipping: false }];
const DEVICE_DAYS: number = (catalog.site as any).membership?.device_days ?? 90;
export const COOKIE = 'ep_member';
const CODE_MINUTES = 10, MAX_ATTEMPTS = 5, MAX_SENDS_PER_HOUR = 3;

const enc = new TextEncoder();
async function sha256(s: string): Promise<string> {
  const d = await crypto.subtle.digest('SHA-256', enc.encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
const norm = (email: string) => email.trim().toLowerCase();

/* Paid orders for an email, product total after member discount (refunded and unpaid orders excluded). */
export async function history(db: D1Database, email: string, excludeOrderId?: string): Promise<PaidOrder[]> {
  const r = await db.prepare(`SELECT id, created_at, subtotal_cents - COALESCE(discount_cents, 0) AS cents FROM orders
                              WHERE email = ? AND status = 'paid'`).bind(norm(email)).all<{ id: string; created_at: string; cents: number }>();
  return (r.results ?? []).filter((o) => o.id !== excludeOrderId).map((o) => ({ at: o.created_at, cents: Number(o.cents) }));
}
export async function statusFor(db: D1Database, email: string, excludeOrderId?: string, now?: Date): Promise<Status> {
  return statusAt(LEVELS, await history(db, email, excludeOrderId), now);
}

/* ---- remembered devices ---- */
export async function verifiedEmail(db: D1Database, token: string | undefined): Promise<string | null> {
  if (!token || token.length < 32) return null;
  const r = await db.prepare(`SELECT email FROM member_devices WHERE token_hash = ? AND expires_at > ?`)
    .bind(await sha256(token), new Date().toISOString()).first<{ email: string }>();
  return r?.email ?? null;
}
async function newDevice(db: D1Database, email: string): Promise<{ token: string; maxAge: number }> {
  const token = [...crypto.getRandomValues(new Uint8Array(32))].map((b) => b.toString(16).padStart(2, '0')).join('');
  const now = new Date(), exp = new Date(now.getTime() + DEVICE_DAYS * 86_400_000);
  await db.prepare(`INSERT INTO member_devices (token_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)`)
    .bind(await sha256(token), norm(email), now.toISOString(), exp.toISOString()).run();
  return { token, maxAge: DEVICE_DAYS * 86_400 };
}

/* ---- one-time codes ---- */
export async function issueCode(env: Env, email: string): Promise<{ ok: boolean; devCode?: string; error?: string }> {
  const e = norm(email), now = new Date();
  const row = await env.DB.prepare(`SELECT sends, window_start FROM member_codes WHERE email = ?`).bind(e).first<{ sends: number; window_start: string }>();
  const inWindow = row && now.getTime() - Date.parse(row.window_start) < 3_600_000;
  if (inWindow && row!.sends >= MAX_SENDS_PER_HOUR) return { ok: false, error: 'Too many codes requested. Try again in an hour.' };
  const code = String(crypto.getRandomValues(new Uint32Array(1))[0] % 1_000_000).padStart(6, '0');
  await env.DB.prepare(`INSERT INTO member_codes (email, code_hash, expires_at, attempts, sends, window_start) VALUES (?, ?, ?, 0, 1, ?)
                        ON CONFLICT(email) DO UPDATE SET code_hash = excluded.code_hash, expires_at = excluded.expires_at, attempts = 0,
                          sends = CASE WHEN ? THEN member_codes.sends + 1 ELSE 1 END,
                          window_start = CASE WHEN ? THEN member_codes.window_start ELSE excluded.window_start END`)
    .bind(e, await sha256(`${e}:${code}`), new Date(now.getTime() + CODE_MINUTES * 60_000).toISOString(), now.toISOString(), inWindow ? 1 : 0, inWindow ? 1 : 0).run();
  if (!env.RESEND_API_KEY) {
    if ((env.PAYMENT_MODE ?? 'stub') === 'stub') return { ok: true, devCode: code };   // local test mode only
    return { ok: false, error: 'Member pricing is not available right now.' };
  }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST', headers: { authorization: `Bearer ${env.RESEND_API_KEY}`, 'content-type': 'application/json' },
    body: JSON.stringify({
      from: env.MEMBER_EMAIL_FROM ?? 'Energy Peptides <codes@energypeptides.us>', to: [e],
      subject: `Your Energy Peptides code: ${code}`,
      text: `Your Energy Peptides verification code is ${code}.\n\nIt expires in ${CODE_MINUTES} minutes. Enter it at checkout to see your status and member pricing. If you did not request it, ignore this email.`,
    }),
    signal: AbortSignal.timeout(8000),
  }).catch(() => null);
  if (!res?.ok) { console.error('[member] resend', res?.status); return { ok: false, error: 'The code could not be sent. Try again shortly.' }; }
  return { ok: true };
}

export async function checkCode(db: D1Database, email: string, code: string): Promise<{ ok: boolean; token?: string; maxAge?: number; error?: string }> {
  const e = norm(email);
  const row = await db.prepare(`SELECT code_hash, expires_at, attempts FROM member_codes WHERE email = ?`).bind(e)
    .first<{ code_hash: string; expires_at: string; attempts: number }>();
  if (!row || Date.parse(row.expires_at) < Date.now()) return { ok: false, error: 'That code has expired. Request a new one.' };
  if (row.attempts >= MAX_ATTEMPTS) return { ok: false, error: 'Too many attempts. Request a new code.' };
  if (row.code_hash !== (await sha256(`${e}:${String(code).trim()}`))) {
    await db.prepare(`UPDATE member_codes SET attempts = attempts + 1 WHERE email = ?`).bind(e).run();
    return { ok: false, error: 'That code is not right. Check the email and try again.' };
  }
  await db.prepare(`DELETE FROM member_codes WHERE email = ?`).bind(e).run();
  return { ok: true, ...(await newDevice(db, e)) };
}
