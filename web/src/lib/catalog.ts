import data from '../data/catalog.json';

export type Catalog = typeof data;
export type Product = Catalog['products'][number];
export type Faq = Catalog['faq'][number];

export const catalog: Catalog = data;
export const site = data.site;
export const products: Product[] = data.products;
export const productsBySlug = new Map(products.map((p) => [p.slug, p]));
export const productsBySku = new Map(products.map((p) => [p.sku, p]));

export function sizeLabel(p: Pick<Product, 'size_mg' | 'size_ml'>): string {
  if (p.size_mg) return `${p.size_mg} mg`;
  if (p.size_ml) return `${p.size_ml} ml`;
  return '';
}
export function unitLabel(_p?: Product): string {
  return 'per vial';   // everything is sold by the single vial (2026-09-10)
}
export function familyName(p: Product): string {
  return p.display_name || p.components.map((c) => c.name).join(' / ') || p.name;
}
export function isBlend(p: Product): boolean { return p.components.length > 1; }
/* Blends always show every component and its amount (BR-CATEGORIES), largest first. */
export function compositionLine(p: Product): string {
  if (!isBlend(p)) return '';
  return [...p.components].sort((a, b) => (b.amount_mg ?? 0) - (a.amount_mg ?? 0))
    .map((c) => (c.amount_mg ? `${c.name} ${c.amount_mg} mg` : c.name)).join(' · ');
}
/* Text as printed on the vial label: nickname, or components joined with + */
export function labelName(p: Product): string {
  return p.display_name || p.components.map((c) => c.name).join(' + ') || p.name;
}
export function labelAmount(p: Product): string {
  const base = sizeLabel(p);
  if (isBlend(p) && !p.display_name && p.components.every((c) => c.amount_mg)) return `${base} (${p.components.map((c) => c.amount_mg).join('+')})`;
  return base;
}
export function cents(usd: number | null | undefined): number {
  return Math.round(Number(usd ?? 0) * 100);
}
export function money(c: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(c / 100);
}
export function shippingCents(subtotal: number): number {
  const free = cents(site.free_shipping_over_usd);
  return subtotal >= free ? 0 : cents(site.shipping_usd);
}
/* Browse by composition (brand copy rules §05): grouped by what a compound is, never by intended use. */
export const compositionClasses = (() => {
  const m = new Map<string, { name: string; slug: string; products: (Product & { family: string })[] }>();
  for (const p of products) {
    const g = m.get(p.composition_slug) ?? { name: p.composition_class, slug: p.composition_slug, products: [] };
    g.products.push({ ...p, family: familyName(p) });
    m.set(p.composition_slug, g);
  }
  return [...m.values()].sort((a, b) => (a.products[0].category === 'accessory' ? 1 : 0) - (b.products[0].category === 'accessory' ? 1 : 0) || a.name.localeCompare(b.name));
})();
