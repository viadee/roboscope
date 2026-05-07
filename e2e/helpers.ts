/**
 * Shared helpers for RoboScope E2E tests.
 */
import { type Page, expect } from '@playwright/test';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

/**
 * Mark first-login complete server-side. The router (`router/index.ts`)
 * intercepts every navigation when `auth.user.first_login_complete === false`
 * and redirects to `/welcome`, which would derail every test that expects
 * to land on /dashboard / /repos / etc. Fresh test DBs always start with
 * the flag unset for the seeded admin user, so each test has to clear it
 * before navigating.
 *
 * Idempotent — calling it twice is a no-op on the second call. We swallow
 * non-200 responses so a backend that doesn't ship the endpoint yet
 * (older release) doesn't fail the whole suite.
 */
async function markFirstLoginComplete(page: Page, accessToken: string): Promise<void> {
  try {
    await page.request.post(`${API}/auth/first-login/complete`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      data: {},
    });
  } catch {
    /* endpoint not present on this build → harmless */
  }
}

/**
 * Login via API and inject tokens into localStorage so the Vue app is authenticated.
 */
export async function loginViaApi(page: Page): Promise<void> {
  // Call login API directly
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  const body = await res.json();

  // Mark the first-login flag BEFORE we navigate — otherwise the router
  // will intercept the very first /dashboard goto and bounce to /welcome.
  await markFirstLoginComplete(page, body.access_token);

  // Navigate to the app so we can set localStorage on the right origin
  await page.goto('/login');

  // Inject tokens + suppress tour auto-start
  await page.evaluate((tokens) => {
    localStorage.setItem('access_token', tokens.access_token);
    localStorage.setItem('refresh_token', tokens.refresh_token);
    localStorage.setItem('roboscope_tour_completed', 'true');
  }, body);
}

/**
 * Login via API and navigate to dashboard. Waits until the dashboard heading is visible.
 */
export async function loginAndGoToDashboard(page: Page): Promise<void> {
  await loginViaApi(page);
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
}

/**
 * Login via the UI form. Marks first-login complete BEFORE filling the
 * form so the post-login navigation lands at /dashboard (the actual login
 * response carries the freshly-flipped flag in the user payload, so the
 * router doesn't redirect to /welcome).
 */
export async function loginViaUi(page: Page, email = EMAIL, password = PASSWORD): Promise<void> {
  // Get an access token via the API to clear the first-login flag
  // server-side. This mirrors what loginViaApi does — we just don't
  // inject tokens, so the UI flow proceeds normally afterwards.
  const apiRes = await page.request.post(`${API}/auth/login`, {
    data: { email, password },
  });
  if (apiRes.ok()) {
    const apiBody = await apiRes.json();
    await markFirstLoginComplete(page, apiBody.access_token);
  }

  await page.goto('/login');
  await page.getByPlaceholder('admin@roboscope.local').fill(email);
  await page.getByPlaceholder('Passwort').fill(password);
  await page.getByRole('button', { name: 'Anmelden' }).click();
}
