import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testIgnore: process.env.CI ? ['**/take-screenshots.spec.ts'] : [],
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 15_000,

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    actionTimeout: 8_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
