import type { Env } from '../env';
import type { PaymentAdapter } from './types';
import { stubAdapter } from './stub';
import { tagadaAdapter } from './tagada';

export function paymentAdapter(env: Env): PaymentAdapter {
  if (env.PAYMENT_MODE === 'tagada') {
    if (!env.TAGADA_API_KEY || !env.TAGADA_STORE_ID) throw new Error('PAYMENT_MODE=tagada but TAGADA_API_KEY / TAGADA_STORE_ID are not set');
    return tagadaAdapter({ apiKey: env.TAGADA_API_KEY, storeId: env.TAGADA_STORE_ID, baseUrl: env.TAGADA_BASE_URL, paymentFlowId: env.TAGADA_PAYMENT_FLOW_ID });
  }
  return stubAdapter;
}
