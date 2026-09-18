/* Server-side twin of src/lib/ordering.ts. Read at request time, so flipping the vars closes or opens
   the checkout API without a rebuild — and so a stale static page can never be used to place an order
   the processor cannot actually charge. Keep the two rules in step. */
import type { Env } from './env';

export function orderingOpen(env: Env): boolean {
  if (env.ORDERING === 'open') return true;
  return (env.TAGADA_ENV ?? 'test').toLowerCase() === 'live';
}
