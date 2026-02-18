import { test as base, Page, BrowserContext } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const AUTH_STATE_PATH = path.join(__dirname, '..', '.auth-state.json');

/** Shape of the persisted auth state written by global-setup. */
interface AuthState {
  authenticated: boolean;
  access_token?: string;
  refresh_token?: string;
  user?: {
    id: number;
    email: string;
    username: string;
    role: string;
    is_active: boolean;
  };
}

/**
 * Read the auth state saved by global-setup.
 * Returns null when the file does not exist or the state is not authenticated.
 */
function readAuthState(): AuthState | null {
  try {
    const raw = fs.readFileSync(AUTH_STATE_PATH, 'utf-8');
    const state: AuthState = JSON.parse(raw);
    return state.authenticated ? state : null;
  } catch {
    return null;
  }
}

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
  email = 'admin@mateox.local',
  password = 'admin',
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

    const savedState = readAuthState();
    if (savedState && savedState.access_token && savedState.refresh_token) {
      await injectTokensIntoPage(page, savedState.access_token, savedState.refresh_token);
    } else {
      // Fall back to a fresh API login
      await loginViaApi(page);
    }

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
