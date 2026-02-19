import { test, expect } from '@playwright/test';
import { loginViaApi, loginViaUi, loginAndGoToDashboard } from '../helpers';

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any existing auth state
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    });
  });

  test('should show login page with form', async ({ page }) => {
    await page.goto('/login');

    // Heading "Anmelden"
    await expect(page.locator('h2', { hasText: 'Anmelden' })).toBeVisible();

    // Email and password inputs
    await expect(page.getByPlaceholder('admin@roboscope.local')).toBeVisible();
    await expect(page.getByPlaceholder('Passwort')).toBeVisible();

    // Submit button
    await expect(page.getByRole('button', { name: 'Anmelden' })).toBeVisible();

    // Hint text
    await expect(page.getByText('Standard: admin@roboscope.local / admin123')).toBeVisible();
  });

  test('should login with valid credentials via UI and redirect to dashboard', async ({ page }) => {
    await loginViaUi(page);

    // Should redirect to /dashboard
    await page.waitForURL('**/dashboard', { timeout: 10_000 });
    expect(page.url()).toContain('/dashboard');

    // Dashboard heading should be visible
    await expect(page.locator('h1', { hasText: 'Dashboard' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.goto('/login');
    await page.getByPlaceholder('admin@roboscope.local').fill('wrong@example.com');
    await page.getByPlaceholder('Passwort').fill('wrongpassword123');
    await page.getByRole('button', { name: 'Anmelden' }).click();

    // Error message should appear as .error-text
    // The backend rejects with 401 "Invalid email or password"
    await expect(page.locator('.error-text')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.error-text')).toContainText(/Invalid|fehlgeschlagen/i);
  });

  test('should prevent submission with empty fields (HTML5 validation)', async ({ page }) => {
    await page.goto('/login');

    // Click submit without filling fields
    await page.getByRole('button', { name: 'Anmelden' }).click();

    // Should still be on login page (HTML5 required prevents submission)
    expect(page.url()).toContain('/login');
    await expect(page.locator('h2', { hasText: 'Anmelden' })).toBeVisible();
  });

  test('should redirect to login when accessing protected page without auth', async ({ page }) => {
    // Try to access dashboard directly without being authenticated
    await page.goto('/dashboard');

    // Should be redirected to /login
    await page.waitForURL('**/login**', { timeout: 5_000 });
    expect(page.url()).toContain('/login');
  });

  test('should logout and redirect to login page', async ({ page }) => {
    // First login
    await loginAndGoToDashboard(page);
    await expect(page.locator('h1', { hasText: 'Dashboard' })).toBeVisible({ timeout: 10_000 });

    // Click "Abmelden" button in the header
    const logoutButton = page.getByRole('button', { name: 'Abmelden' });
    await expect(logoutButton).toBeVisible();
    await logoutButton.click();

    // Should redirect to login
    await page.waitForURL('**/login', { timeout: 5_000 });
    await expect(page.locator('h2', { hasText: 'Anmelden' })).toBeVisible();

    // Tokens should be cleared
    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(accessToken).toBeNull();
  });

  test('should login via API and inject tokens correctly', async ({ page }) => {
    await loginViaApi(page);
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Should be on dashboard (not redirected to login)
    expect(page.url()).toContain('/dashboard');
    await expect(page.locator('h1', { hasText: 'Dashboard' })).toBeVisible({ timeout: 10_000 });
  });
});
