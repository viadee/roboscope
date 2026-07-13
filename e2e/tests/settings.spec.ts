import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should load settings page with heading', async ({ page }) => {
    // Settings is nested under the collapsible "Mehr" group as of
    // 0.9.0 — expand it before clicking the entry.
    await page.locator('.nav-more-toggle').click();
    await page.locator('.nav-item', { hasText: 'Einstellungen' }).click();
    await page.waitForURL('**/settings');

    await expect(page.locator('h1', { hasText: 'Einstellungen' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show tabs for Allgemein and Benutzer', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('h1', { hasText: 'Einstellungen' })).toBeVisible({ timeout: 10_000 });

    // Both tabs should be visible. Target the .tab buttons specifically — the
    // General tab also renders a localized "Allgemein" category card now, so a
    // bare getByText('Allgemein') is ambiguous (strict-mode violation).
    await expect(page.locator('.tab', { hasText: 'Allgemein' })).toBeVisible();
    await expect(page.locator('.tab', { hasText: 'Benutzer' })).toBeVisible();
  });

  test('should switch to Benutzer tab and show users table', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('h1', { hasText: 'Einstellungen' })).toBeVisible({ timeout: 10_000 });

    // Click Benutzer tab
    await page.locator('.tab', { hasText: 'Benutzer' }).click();

    // Should show a users table with the admin user
    await page.waitForLoadState('networkidle');

    // The admin user should appear
    await expect(page.getByText('admin@roboscope.local')).toBeVisible({ timeout: 5_000 });
  });
});
