// @ts-check
import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';

import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://energypeptides.us',

  // pages are static; /api/* routes opt in with `prerender = false`
  output: 'static',

  adapter: cloudflare({ platformProxy: { enabled: true } }),

  integrations: [
    // Cart and checkout are transactional, not content: /checkout/ is a noindex redirect while
    // ordering is closed, and neither belongs in search results once it reopens.
    sitemap({ filter: (page) => !page.includes('/cart') && !page.includes('/checkout') }),
  ],
});