import { test as base, Page, BrowserContext } from '@playwright/test';

/**
 * Inject tokens into localStorage for the given page so the Vue app
 * considers the user authenticated on the next navigation.
 */
async function injectTokensIntoPage(
  page: Page,
  accessToken: string,
  refreshToken: string,
): Promise<void> {
  await page.evaluate(
    ({ at, rt }) => {
      localStorage.setItem('access_token', at);
      localStorage.setItem('refresh_token', rt);
    },
    { at: accessToken, rt: refreshToken },
  );
}

/**
 * Perform a fresh login via the API, then inject the resulting tokens into
 * the page's localStorage.
 */
async function loginViaApi(
  page: Page,
  email = 'admin@roboscope.local',
  password = 'admin123',
): Promise<void> {
  const apiBase = process.env.API_BASE_URL || 'http://localhost:8000';
  const response = await page.request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email, password },
  });

  if (!response.ok()) {
    throw new Error(`API login failed with status ${response.status()}`);
  }

  const tokens = await response.json();
  await injectTokensIntoPage(page, tokens.access_token, tokens.refresh_token);
}

// ----- Custom fixtures -----

type AuthFixtures = {
  /** A page that is already authenticated as the admin user. */
  authenticatedPage: Page;
  /** Helper: log in via API and inject tokens for any user. */
  loginAs: (page: Page, email?: string, password?: string) => Promise<void>;
};

/**
 * Extended test object that provides auth-related fixtures.
 *
 * Usage in test files:
 *   import { test, expect } from '../fixtures/auth.fixture';
 */
export const test = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Navigate to the app origin first so localStorage writes go to the right domain.
    await page.goto('/login', { waitUntil: 'domcontentloaded' });

    await loginViaApi(page);

    // Reload so the Vue app picks up the tokens from localStorage
    await page.goto('/dashboard', { waitUntil: 'networkidle' });

    await use(page);
  },

  loginAs: async ({}, use) => {
    await use(async (page: Page, email?: string, password?: string) => {
      await page.goto('/login', { waitUntil: 'domcontentloaded' });
      await loginViaApi(page, email, password);
      await page.goto('/dashboard', { waitUntil: 'networkidle' });
    });
  },
});

export { expect } from '@playwright/test';
