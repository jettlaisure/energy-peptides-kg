import { defineConfig } from '@playwright/test';

// UI-only checks against the production output. No payment or order API is called.
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:4322', headless: true },
  webServer: {
    command: 'python3 -m http.server 4322 --bind 127.0.0.1 --directory dist/client',
    url: 'http://127.0.0.1:4322',
    reuseExistingServer: !process.env.CI,
  },
});
