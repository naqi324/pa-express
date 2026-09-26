import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5175';

const webServer = process.env.E2E_BASE_URL
  ? undefined
  : [
      {
        command: 'uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8004',
        url: 'http://127.0.0.1:8004/api/health',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
      {
        command: 'pnpm dev:frontend',
        url: 'http://127.0.0.1:5175',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
    ];

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  workers: 1,
  expect: {
    timeout: 8_000,
  },
  fullyParallel: true,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    trace: 'retain-on-failure',
  },
  webServer,
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
