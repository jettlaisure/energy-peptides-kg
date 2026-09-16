// Optional local screenshots: npm run build, serve dist/client on :4322, then node tests/preview.mjs.
import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

await mkdir('test-results/previews', { recursive: true });
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  for (const [name, width, height, route] of [
    ['home-desktop', 1440, 1100, '/'],
    ['home-mobile', 390, 1000, '/'],
    ['catalog-desktop', 1440, 1100, '/products/'],
    ['product-desktop', 1440, 1100, '/products/bpc-157-10mg/'],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(`http://127.0.0.1:4322${route}`, { waitUntil: 'networkidle' });
    await page.evaluate(async () => {
      await document.fonts.ready;
      const visibleImages = [...document.images].filter(image => {
        const rect = image.getBoundingClientRect();
        return rect.top < innerHeight && rect.bottom > 0;
      });
      await Promise.all(visibleImages.map(async image => {
        image.loading = 'eager';
        await image.decode();
      }));
    });
    await page.screenshot({ path: `test-results/previews/${name}.png` });
    if (name === 'catalog-desktop') {
      await page.locator('[data-product-card]').first().screenshot({ path: 'test-results/previews/product-card.png' });
    }
  }
} finally {
  await browser.close();
}
