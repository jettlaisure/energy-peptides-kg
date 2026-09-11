/* Kashu/Tagada webhook signature verification. Two envelope styles exist (see docs/tagada-integration.md):
   - public docs:  header X-TagadaPay-Signature: sha256=<hex>, HMAC-SHA256 over the raw body
   - dashboard:    header tagadapay-signature,  same HMAC (constructEvent in the SDK) */
async function hmacHex(secret: string, body: string): Promise<string> {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(body));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}
/* `secrets` may hold several comma-separated signing secrets (sandbox store + live store endpoints). */
export async function verifySignature(rawBody: string, headers: Headers, secrets: string): Promise<boolean> {
  const header = headers.get('x-tagadapay-signature') ?? headers.get('tagadapay-signature') ?? '';
  if (!header) return false;
  for (const secret of secrets.split(',').map((s) => s.trim()).filter(Boolean)) {
    if (await verifyOne(rawBody, header, secret)) return true;
  }
  return false;
}
async function verifyOne(rawBody: string, header: string, secret: string): Promise<boolean> {
  const expected = await hmacHex(secret, rawBody);
  // accept "sha256=<hex>", bare hex, or "t=<ts>,v1=<hex>" (Stripe-style) variants
  const candidates = header.split(',').map((part) => part.trim().replace(/^(sha256=|v1=)/, '')).filter((p) => /^[0-9a-f]{64}$/i.test(p));
  return candidates.some((c) => timingSafeEqual(c.toLowerCase(), expected));
}
export interface NormalizedEvent { id: string; type: string; paymentId?: string; orderId?: string; raw: any }
export function normalizeEvent(payload: any): NormalizedEvent {
  const type: string = String(payload?.type ?? '').replace('/', '.');
  const obj = payload?.data?.object ?? payload?.data ?? {};
  return {
    id: String(payload?.id ?? ''), type,
    paymentId: obj.paymentId ?? obj.payment_id ?? (type.startsWith('payment.') ? obj.id : undefined),
    orderId: obj.orderId ?? obj.order_id ?? obj.metadata?.orderId ?? obj.metadata?.cartCustomAttributes?.orderId,
    raw: payload,
  };
}
