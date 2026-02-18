import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Admin Password Reset', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should show password reset button in users tab', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    // Switch to users tab
    await page.getByText('Benutzer').click();
    await page.waitForLoadState('networkidle');

    // Wait for users table to load
    await expect(page.getByText('admin@mateox.local')).toBeVisible({ timeout: 5_000 });

    // Reset password button should be visible
    const resetBtn = page.getByRole('button', { name: /Passwort zurücksetzen/ });
    await expect(resetBtn.first()).toBeVisible();
  });

  test('should open password reset dialog', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    await page.getByText('Benutzer').click();
    await expect(page.getByText('admin@mateox.local')).toBeVisible({ timeout: 5_000 });

    // Click reset password
    await page.getByRole('button', { name: /Passwort zurücksetzen/ }).first().click();

    // Dialog should open with password field
    await expect(page.locator('input[type="password"]')).toBeVisible({ timeout: 3_000 });
  });

  test('should close password reset dialog on cancel', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    await page.getByText('Benutzer').click();
    await expect(page.getByText('admin@mateox.local')).toBeVisible({ timeout: 5_000 });

    // Open dialog
    await page.getByRole('button', { name: /Passwort zurücksetzen/ }).first().click();
    await expect(page.locator('input[type="password"]')).toBeVisible({ timeout: 3_000 });

    // Cancel
    await page.getByRole('button', { name: 'Abbrechen' }).click();
    await expect(page.locator('input[type="password"]')).not.toBeVisible({ timeout: 3_000 });
  });

  test('should require minimum password length', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    await page.getByText('Benutzer').click();
    await expect(page.getByText('admin@mateox.local')).toBeVisible({ timeout: 5_000 });

    // Open dialog
    await page.getByRole('button', { name: /Passwort zurücksetzen/ }).first().click();
    const pwField = page.locator('input[type="password"]');
    await expect(pwField).toBeVisible({ timeout: 3_000 });

    // Password field should have minlength attribute
    await expect(pwField).toHaveAttribute('minlength', '6');
  });
});
