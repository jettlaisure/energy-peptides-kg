// @ts-check
import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';

export default defineConfig({
  site: 'https://energypeptides.us',
  output: 'static',                 // pages are static; /api/* routes opt in with `prerender = false`
  adapter: cloudflare({ platformProxy: { enabled: true } }),
});
