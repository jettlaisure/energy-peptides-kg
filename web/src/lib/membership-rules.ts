/* Membership status rules, pure: no database, no Cloudflare. Shared by the checkout API, the order alert and the tests.
   Spend = paid product total after member discount, rolling 12 months; shipping and refunded orders are excluded.
   A level is reached the moment rolling spend crosses its threshold, holds for 12 months after that order, and when the
   hold ends the customer drops at most one level per year. See site.yaml `membership` and the program doc. */
export interface Level { name: string; min_usd: number; discount_pct: number; free_shipping: boolean }
export interface PaidOrder { at: string; cents: number }   // ISO time, product total after discount
export interface Status {
  level: number;              // index into levels
  name: string;
  spend12: number;            // cents, rolling 12 months to `now`
  holdsUntil: string | null;  // ISO date the current level is held through (null for the base level)
  next: { name: string; toGo: number } | null;   // cents still to spend; null at the top level
}

const DAY = 86_400_000, YEAR = 365 * DAY;

export function levelForSpend(levels: Level[], cents: number): number {
  let i = 0;
  levels.forEach((l, k) => { if (cents >= Math.round(l.min_usd * 100)) i = k; });
  return i;
}

/* Level earned at each order: rolling 12-month spend up to and including that order. */
function earned(levels: Level[], orders: PaidOrder[]): { t: number; level: number }[] {
  const os = orders.map((o) => ({ t: Date.parse(o.at), c: o.cents })).filter((o) => Number.isFinite(o.t)).sort((a, b) => a.t - b.t);
  return os.map((o) => ({ t: o.t, level: levelForSpend(levels, os.filter((x) => x.t > o.t - YEAR && x.t <= o.t).reduce((n, x) => n + x.c, 0)) }));
}

export function statusAt(levels: Level[], orders: PaidOrder[], now: Date = new Date()): Status {
  const n = now.getTime();
  const e = earned(levels, orders).filter((x) => x.t <= n);
  const held = e.filter((x) => x.t > n - YEAR);
  const prior = e.filter((x) => x.t > n - 2 * YEAR && x.t <= n - YEAR);
  const heldLevel = Math.max(0, ...held.map((x) => x.level));
  const softLevel = Math.max(0, Math.max(0, ...prior.map((x) => x.level)) - 1);
  const level = Math.max(heldLevel, softLevel);
  let holdsUntil: string | null = null;
  if (level > 0) {
    const fromHeld = held.filter((x) => x.level >= level).map((x) => x.t + YEAR);
    const fromSoft = level === softLevel ? prior.filter((x) => x.level >= level + 1).map((x) => x.t + 2 * YEAR) : [];
    const until = Math.max(...fromHeld, ...fromSoft);
    holdsUntil = new Date(until).toISOString().slice(0, 10);
  }
  const spend12 = orders.filter((o) => { const t = Date.parse(o.at); return t > n - YEAR && t <= n; }).reduce((s, o) => s + o.cents, 0);
  const nextIdx = level + 1 < levels.length ? level + 1 : -1;
  const next = nextIdx < 0 ? null : { name: levels[nextIdx].name, toGo: Math.max(0, Math.round(levels[nextIdx].min_usd * 100) - spend12) };
  return { level, name: levels[level].name, spend12, holdsUntil, next };
}

/* Pricing for a cart at a given level: discount on products, free shipping for members, else the store rule. */
export function price(levels: Level[], level: number, subtotal: number, storeShipping: (net: number) => number) {
  const l = levels[level] ?? levels[0];
  const discount = Math.round((subtotal * l.discount_pct) / 100);
  const net = subtotal - discount;
  const shipping = l.free_shipping ? 0 : storeShipping(net);
  return { discount, net, shipping, total: net + shipping };
}

/* The progress line shown at checkout. Plain words, no urgency (program doc, "The progress meter"). */
export function progressLine(levels: Level[], s: Status, cartNet: number): string {
  if (!s.next) return `${s.name} status${s.holdsUntil ? ` through ${monthYear(s.holdsUntil)}` : ''}.`;
  const nextLevel = levels.find((l) => l.name === s.next!.name)!;
  const have = s.level > 0 && s.holdsUntil ? `${s.name} status through ${monthYear(s.holdsUntil)}. ` : '';
  if (cartNet >= s.next.toGo) return `${have}This order takes you to ${s.next.name}.`;
  const perk = `${nextLevel.discount_pct}% off${nextLevel.free_shipping ? ' and free shipping on every order' : ''}`;
  const usd = (c: number) => `$${Math.ceil(c / 100).toLocaleString('en-US')}`;
  if (s.next.toGo <= Math.round(nextLevel.min_usd * 100) * 0.25) return `${have}${usd(s.next.toGo)} from ${s.next.name}: ${perk}.`;
  return `${have}${s.next.name} status at ${usd(nextLevel.min_usd * 100)} in 12 months. You're at ${usd(s.spend12)}.`;
}

export function monthYear(isoDate: string): string {
  return new Date(isoDate + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
}
