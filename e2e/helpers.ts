/**
 * Shared helpers for mateoX E2E tests.
 */
import { type Page, expect } from '@playwright/test';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@mateox.local';
const PASSWORD = 'admin123';

/**
 * Login via API and inject tokens into localStorage so the Vue app is authenticated.
 */
export async function loginViaApi(page: Page): Promise<void> {
  // Call login API directly
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  const body = await res.json();

  // Navigate to the app so we can set localStorage on the right origin
  await page.goto('/login');

  // Inject tokens
  await page.evaluate((tokens) => {
    localStorage.setItem('access_token', tokens.access_token);
    localStorage.setItem('refresh_token', tokens.refresh_token);
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
 * Login via the UI form.
 */
export async function loginViaUi(page: Page, email = EMAIL, password = PASSWORD): Promise<void> {
  await page.goto('/login');
  await page.getByPlaceholder('admin@mateox.local').fill(email);
  await page.getByPlaceholder('Passwort').fill(password);
  await page.getByRole('button', { name: 'Anmelden' }).click();
}
