/* Cloudflare bindings and env vars. Secrets come from `wrangler secret put` (prod) or .dev.vars (local). */
import { env as cfEnv } from 'cloudflare:workers';

export interface Env {
  DB: D1Database;
  PAYMENT_MODE?: string;          // stub | tagada
  TAGADA_API_KEY?: string;
  TAGADA_STORE_ID?: string;
  TAGADA_WEBHOOK_SECRET?: string;
  TAGADA_BASE_URL?: string;
  TAGADA_ENV?: string;            // test | live
  TAGADA_PAYMENT_FLOW_ID?: string; // optional explicit flow (needed if the store has none attached)
}
export function getEnv(): Env { return cfEnv as unknown as Env; }
