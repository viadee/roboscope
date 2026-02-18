import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Environments Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should load environments page with heading', async ({ page }) => {
    await page.locator('.nav-item', { hasText: 'Umgebungen' }).click();
    await page.waitForURL('**/environments');

    await expect(page.locator('h1', { hasText: 'Umgebungen' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show add environment button', async ({ page }) => {
    await page.goto('/environments');
    await expect(page.locator('h1', { hasText: 'Umgebungen' })).toBeVisible({ timeout: 10_000 });

    const addButton = page.getByRole('button', { name: /Neue Umgebung/ });
    await expect(addButton).toBeVisible();
  });

  test('should open and close new environment modal', async ({ page }) => {
    await page.goto('/environments');
    await expect(page.locator('h1', { hasText: 'Umgebungen' })).toBeVisible({ timeout: 10_000 });

    // Open modal
    await page.getByRole('button', { name: /Neue Umgebung/ }).click();

    // Form fields should appear
    await expect(page.getByPlaceholder('production')).toBeVisible({ timeout: 3_000 });
    // Use exact: true to avoid matching "python:3.12-slim" too
    await expect(page.getByPlaceholder('3.12', { exact: true })).toBeVisible();

    // Cancel
    await page.getByRole('button', { name: 'Abbrechen' }).click();
    await expect(page.getByPlaceholder('production')).not.toBeVisible({ timeout: 3_000 });
  });
});
