/* Browser-side cart. Quantities only; prices are always re-read from the catalog, never trusted from storage. */
export type CartLine = { sku: string; qty: number };
const KEY = 'ep-cart-v1';

export function readCart(): CartLine[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as CartLine[]) : [];
    return parsed.filter((l) => l && typeof l.sku === 'string' && Number.isInteger(l.qty) && l.qty > 0);
  } catch { return []; }
}
export function writeCart(lines: CartLine[]) {
  try { localStorage.setItem(KEY, JSON.stringify(lines)); } catch { /* private mode: cart is per-page then */ }
  document.dispatchEvent(new CustomEvent('cart:change', { detail: { count: lines.reduce((n, l) => n + l.qty, 0) } }));
}
export function addToCart(sku: string, qty = 1) {
  const lines = readCart();
  const hit = lines.find((l) => l.sku === sku);
  if (hit) hit.qty = Math.min(hit.qty + qty, 20); else lines.push({ sku, qty: Math.min(qty, 20) });
  writeCart(lines);
}
export function setQty(sku: string, qty: number) {
  const lines = readCart().map((l) => (l.sku === sku ? { ...l, qty } : l)).filter((l) => l.qty > 0);
  writeCart(lines);
}
export function clearCart() { writeCart([]); }
export function cartCount(): number { return readCart().reduce((n, l) => n + l.qty, 0); }
