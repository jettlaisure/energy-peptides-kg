import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import type { Catalog } from '../src/lib/catalog';
const catalog = JSON.parse(readFileSync(new URL('../src/data/catalog.json', import.meta.url), 'utf8')) as Catalog;

const visibleCards = '[data-product-card]:visible';

test('homepage preserves the compound catalog and links to every composition class', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('Research-grade peptides');
  await expect(page.locator('[data-product-card]')).toHaveCount(catalog.products.filter(p => p.category !== 'accessory').length);
  for (const link of await page.locator('.classes a').all()) {
    const href = await link.getAttribute('href');
    expect(href).toMatch(/^\/products\/#.+/);
  }
  await expect(page.getByRole('link', { name: 'Explore the catalog' })).toHaveAttribute('href', '/products/');
});

test('catalog search tolerates punctuation and supports empty, reset, and stock states', async ({ page }) => {
  await page.goto('/products/');
  const search = page.getByLabel('Find a compound');
  await expect(page.locator(visibleCards)).toHaveCount(catalog.products.length);
  await search.fill('BPC157');
  const expected = catalog.products.filter(p => `${p.name} ${p.components.map(c => c.name).join(' ')}`.replace(/[^a-z0-9]/gi, '').toLowerCase().includes('bpc157'));
  await expect(page.locator(visibleCards)).toHaveCount(expected.length);
  await search.fill('no-such-compound');
  await expect(page.locator(visibleCards)).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'No matching products' })).toBeVisible();
  await page.getByRole('button', { name: 'Show all products' }).click();
  await expect(search).toBeFocused();
  await expect(page.locator(visibleCards)).toHaveCount(catalog.products.length);
  await page.getByLabel('In stock only').check();
  await expect(page.locator(visibleCards)).toHaveCount(catalog.products.filter(p => p.in_stock && p.status === 'active').length);
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.locator(visibleCards)).toHaveCount(catalog.products.length);
});

test('composition navigation clears filters and keeps anchor targets reachable', async ({ page }) => {
  await page.goto('/products/');
  await page.getByLabel('Find a compound').fill('no-such-compound');
  await page.getByRole('link', { name: 'Laboratory supplies', exact: true }).first().click();
  await expect(page.locator('#supplies')).toBeVisible();
  await expect(page.getByLabel('Find a compound')).toHaveValue('');
});

test('mobile menu works with keyboard and closes on Escape', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const menu = page.getByLabel('Toggle navigation');
  await menu.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).not.toBeVisible();
  await expect(menu).toBeFocused();
  await menu.click();
  await page.getByRole('navigation', { name: 'Mobile navigation' }).getByRole('link', { name: 'Catalog' }).click();
  await expect(page).toHaveURL(/\/products\//);
});

test('add-to-cart updates quantity and preserves it across navigation', async ({ page }) => {
  const product = catalog.products.find(p => p.in_stock && p.status === 'active')!;
  await page.goto(`/products/${product.slug}/`);
  await page.getByRole('spinbutton', { name: 'Quantity', exact: true }).fill('2');
  await page.getByRole('button', { name: 'Add to cart', exact: true }).click();
  await expect(page.locator('[data-cart-count]')).toHaveText('2');
  await expect(page.locator('[data-added]')).toBeVisible();
  await page.locator('[data-added] a').click();
  await expect(page.locator('[data-lines] tr')).toHaveCount(1);
  await expect(page.locator('[data-qty]')).toHaveValue('2');
  await expect(page.locator('[data-cart-count]')).toHaveText('2');
  await page.getByRole('button', { name: `Remove ${product.name}` }).click();
  await expect(page.locator('[data-empty]')).toBeVisible();
  await expect(page.locator('[data-totals]')).not.toBeVisible();
});

test('unavailable products cannot be added', async ({ page }) => {
  const product = catalog.products.find(p => !p.in_stock || p.status !== 'active')!;
  await page.goto(`/products/${product.slug}/`);
  await expect(page.locator('[data-add-to-cart] button')).toBeDisabled();
});

test('main pages fit mobile, tablet, and desktop widths', async ({ page }) => {
  test.setTimeout(180_000); // Twenty navigations; allow slower single-core CI machines.
  const product = catalog.products.find(p => p.slug === 'bpc-157-tb-500-20mg')!;
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ['/', '/products/', `/products/${product.slug}/`, '/faq/', '/cart/']) {
      await page.goto(route);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      expect(overflow, `${route} overflows at ${width}px`).toBe(false);
    }
  }
});

test('catalog and mobile navigation remain usable without JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4322/products/');
  await expect(page.locator(visibleCards)).toHaveCount(catalog.products.length);
  await expect(page.locator('[data-catalog-tools]')).not.toBeVisible();
  await page.getByLabel('Toggle navigation').click();
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible();
  await context.close();
});
