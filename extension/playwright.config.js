// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './test/e2e',
  testMatch: '**/*.spec.js',
  timeout: 60000,
  expect: { timeout: 10000 },
  fullyParallel: false,       // Extensions share state; run serially
  retries: 0,
  workers: 1,                 // One browser instance at a time
  reporter: [['html', { open: 'never' }], ['list']],
  use: {
    trace: 'on-first-retry',
    ...(process.env.DOCKER ? {
      launchOptions: {
        args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
      },
    } : {}),
  },
});
