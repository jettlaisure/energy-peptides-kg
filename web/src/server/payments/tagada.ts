/* Kashu Pay (white-label TagadaPay) — Path A, direct server-to-server.
   Browser tokenises the card with @tagadapay/core-js; we exchange the token for a payment instrument,
   optionally open a 3DS session, then process the charge. Docs: ../../docs/tagada-integration.md */
import type { PaymentAdapter, ChargeRequest, ChargeResult } from './types';

export function tagadaAdapter(cfg: { apiKey: string; storeId: string; baseUrl?: string; paymentFlowId?: string }): PaymentAdapter {
  const base = (cfg.baseUrl ?? 'https://api.tagada.io').replace(/\/$/, '') + '/api/public/v1';
  async function call<T>(path: string, body?: unknown, method = 'POST'): Promise<T> {
    const res = await fetch(base + path, {
      method, headers: { authorization: `Bearer ${cfg.apiKey}`, 'content-type': 'application/json', accept: 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const json: any = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json?.error?.message ?? json?.message ?? `Tagada ${path} failed (${res.status})`);
    return json as T;
  }
  return {
    mode: 'tagada',
    async charge(req: ChargeRequest): Promise<ChargeResult> {
      try {
        const inst = await call<{ paymentInstrument: { id: string }; customer: { id: string } }>('/payment-instruments/create-from-token', {
          tagadaToken: req.tagadaToken, storeId: cfg.storeId,
          customerData: { email: req.customer.email, firstName: req.customer.firstName, lastName: req.customer.lastName },
        });
        // Optional 3DS pre-session (recommended for EU SCA). Best-effort: /payments/process handles 3DS
        // challenges itself, and flows with 3DS disabled (e.g. sandbox) reject the pre-session.
        let threedsSessionId: string | undefined;
        if (req.scaRequired) {
          try {
            const s = await call<{ id: string }>('/threeds/create-session', {
              provider: 'basis_theory', storeId: cfg.storeId, paymentInstrumentId: inst.paymentInstrument.id,
              sessionData: { amount: req.amountCents, currency: req.currency, customerEmail: req.customer.email, customerName: `${req.customer.firstName} ${req.customer.lastName}`, storeId: cfg.storeId },
            });
            threedsSessionId = s.id;
          } catch { threedsSessionId = undefined; }
        }
        const addr = req.address ? { line1: req.address.line1, line2: req.address.line2 || undefined, city: req.address.city, state: req.address.state, postalCode: req.address.postalCode, country: req.address.country } : undefined;
        const out = await call<{ payment: { id: string; status: string; requireAction?: string | boolean; requireActionData?: { redirectUrl?: string } } }>('/payments/process', {
          paymentInstrumentId: inst.paymentInstrument.id, customerId: inst.customer.id, storeId: cfg.storeId,
          amount: req.amountCents, currency: req.currency, paymentMethod: 'card', mode: 'purchase',   // no orderId: that field is Tagada's own order id
          initiatedBy: 'customer', threedsSessionId, returnUrl: req.returnUrl,
          ...(cfg.paymentFlowId ? { paymentFlowId: cfg.paymentFlowId } : {}),
          ...(addr ? { shippingAddress: addr, billingAddress: addr } : {}),
        });
        const p = out.payment;
        if (p.requireAction && p.requireAction !== 'none' && p.requireActionData?.redirectUrl) {
          return { status: 'requires_action', paymentId: p.id, customerId: inst.customer.id, redirectUrl: p.requireActionData.redirectUrl };
        }
        if (['succeeded', 'captured', 'paid'].includes(p.status)) return { status: 'paid', paymentId: p.id, customerId: inst.customer.id };
        if (['pending', 'processing', 'authorized'].includes(p.status)) return { status: 'requires_action', paymentId: p.id, customerId: inst.customer.id, redirectUrl: req.returnUrl };
        return { status: 'failed', paymentId: p.id, error: `Payment ${p.status}` };
      } catch (e: any) {
        return { status: 'failed', error: e?.message ?? 'Payment failed' };
      }
    },
    async status(paymentId) {
      const out = await call<{ payment?: { status: string }; status?: string }>(`/payments/${encodeURIComponent(paymentId)}`, undefined, 'GET');
      const s = out.payment?.status ?? out.status ?? '';
      if (['succeeded', 'captured', 'paid'].includes(s)) return 'paid';
      if (['failed', 'declined', 'canceled', 'cancelled', 'rejected'].includes(s)) return 'failed';
      return 'pending';
    },
  };
}
