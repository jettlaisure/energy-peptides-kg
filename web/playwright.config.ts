import { defineConfig } from '@playwright/test';

const port = Number(process.env.UI_TEST_PORT || 4322);
const baseURL = `http://127.0.0.1:${port}`;

// UI-only checks against the production output. No payment or order API is called.
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  use: { baseURL, headless: true },
  webServer: {
    command: `python3 -m http.server ${port} --bind 127.0.0.1 --directory dist/client`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
  },
});
