/* Run: node --test web/tests/membership.test.ts (Node 22.18+ strips the types). */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { statusAt, price, progressLine, levelForSpend, type Level } from '../src/lib/membership-rules.ts';

const L: Level[] = [
  { name: 'Navy', min_usd: 0, discount_pct: 0, free_shipping: false },
  { name: 'Graphite', min_usd: 500, discount_pct: 10, free_shipping: true },
  { name: 'Black', min_usd: 1500, discount_pct: 15, free_shipping: true },
];
const at = (d: string) => new Date(d + 'T12:00:00Z');
const o = (d: string, usd: number) => ({ at: d + 'T12:00:00Z', cents: usd * 100 });
const ship = (net: number) => (net >= 15000 ? 0 : 2495);

test('thresholds', () => {
  assert.equal(levelForSpend(L, 49999), 0);
  assert.equal(levelForSpend(L, 50000), 1);
  assert.equal(levelForSpend(L, 150000), 2);
});

test('a new customer is Navy with the full gap to Graphite', () => {
  const s = statusAt(L, [], at('2027-03-01'));
  assert.deepEqual([s.name, s.spend12, s.holdsUntil, s.next], ['Navy', 0, null, { name: 'Graphite', toGo: 50000 }]);
});

test('the order that crosses the line counts, and the level holds 12 months after it', () => {
  const orders = [o('2027-01-10', 300), o('2027-03-15', 250)];
  const s = statusAt(L, orders, at('2027-03-16'));
  assert.equal(s.name, 'Graphite'); assert.equal(s.holdsUntil, '2028-03-14');
  assert.equal(statusAt(L, orders, at('2028-03-01')).name, 'Graphite');      // spend has fallen below $500, still held
  assert.equal(statusAt(L, orders, at('2028-03-20')).name, 'Navy');          // hold over, Graphite -> Navy is one level
});

test('Black drops one level at a time, never straight to Navy', () => {
  const orders = [o('2027-02-01', 1600)];
  assert.equal(statusAt(L, orders, at('2027-12-01')).name, 'Black');
  const y2 = statusAt(L, orders, at('2028-02-10'));
  assert.equal(y2.name, 'Graphite'); assert.equal(y2.holdsUntil, '2029-01-31');
  assert.equal(statusAt(L, orders, at('2029-02-10')).name, 'Navy');
});

test('refunds are excluded by the caller; only paid totals count', () => {
  assert.equal(statusAt(L, [o('2027-05-01', 499)], at('2027-05-02')).name, 'Navy');
});

test('member pricing: discount on products, free shipping for members', () => {
  assert.deepEqual(price(L, 0, 10000, ship), { discount: 0, net: 10000, shipping: 2495, total: 12495 });
  assert.deepEqual(price(L, 1, 10000, ship), { discount: 1000, net: 9000, shipping: 0, total: 9000 });
  assert.deepEqual(price(L, 2, 19900, ship), { discount: 2985, net: 16915, shipping: 0, total: 16915 });
});

test('progress line wording', () => {
  const far = statusAt(L, [o('2027-04-01', 180)], at('2027-04-02'));
  assert.equal(progressLine(L, far, 5900), "Graphite status at $500 in 12 months. You're at $180.");
  const near = statusAt(L, [o('2027-04-01', 436)], at('2027-04-02'));
  assert.equal(progressLine(L, near, 0), '$64 from Graphite: 10% off and free shipping on every order.');
  assert.equal(progressLine(L, near, 6400), 'This order takes you to Graphite.');
  const mid = statusAt(L, [o('2027-03-10', 570)], at('2027-04-02'));
  assert.equal(progressLine(L, mid, 0), "Graphite status through March 2028. Black status at $1,500 in 12 months. You're at $570.");
  const top = statusAt(L, [o('2027-03-10', 1500)], at('2027-04-02'));
  assert.equal(progressLine(L, top, 0), 'Black status through March 2028.');
});
