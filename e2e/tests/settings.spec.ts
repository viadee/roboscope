import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should load settings page with heading', async ({ page }) => {
    await page.locator('.nav-item', { hasText: 'Einstellungen' }).click();
    await page.waitForURL('**/settings');

    await expect(page.locator('h1', { hasText: 'Einstellungen' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show tabs for Allgemein and Benutzer', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('h1', { hasText: 'Einstellungen' })).toBeVisible({ timeout: 10_000 });

    // Both tabs should be visible
    await expect(page.getByText('Allgemein')).toBeVisible();
    await expect(page.getByText('Benutzer')).toBeVisible();
  });

  test('should switch to Benutzer tab and show users table', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('h1', { hasText: 'Einstellungen' })).toBeVisible({ timeout: 10_000 });

    // Click Benutzer tab
    await page.getByText('Benutzer').click();

    // Should show a users table with the admin user
    await page.waitForLoadState('networkidle');

    // The admin user should appear
    await expect(page.getByText('admin@mateox.local')).toBeVisible({ timeout: 5_000 });
  });
});
