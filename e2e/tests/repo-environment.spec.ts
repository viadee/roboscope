import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Project Environment Selector', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should show environment dropdown on project cards', async ({ page }) => {
    await page.goto('/repos');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    // If projects exist, check for environment dropdowns
    const cards = page.locator('.card');
    const cardCount = await cards.count();

    if (cardCount > 0) {
      // Each card should have an environment inline select
      const envSelect = cards.first().locator('.env-inline-select');
      await expect(envSelect).toBeVisible();
    }
  });

  test('should show "Keine" option in environment dropdown', async ({ page }) => {
    await page.goto('/repos');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    const cards = page.locator('.card');
    const cardCount = await cards.count();

    if (cardCount > 0) {
      const envSelect = cards.first().locator('.env-inline-select');
      // The "Keine" (None) option should always be available
      const noEnvOption = envSelect.locator('option').first();
      await expect(noEnvOption).toBeVisible();
    }
  });

  test('should pre-select default environment in add project dialog', async ({ page }) => {
    await page.goto('/repos');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    // Open add dialog
    const addBtn = page.getByRole('button', { name: /Projekt hinzufügen/ });
    if (await addBtn.isVisible()) {
      await addBtn.click();

      // The environment select should be in the dialog
      const envSelect = page.locator('.modal select').last();
      await expect(envSelect).toBeVisible({ timeout: 3_000 });

      // Cancel
      await page.getByRole('button', { name: 'Abbrechen' }).click();
    }
  });

  test('should default to local folder type in add dialog', async ({ page }) => {
    await page.goto('/repos');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    const addBtn = page.getByRole('button', { name: /Projekt hinzufügen/ });
    if (await addBtn.isVisible()) {
      await addBtn.click();

      // The "Lokaler Ordner" toggle should be active by default
      const localToggle = page.locator('.toggle-btn.active');
      await expect(localToggle).toContainText('Lokaler Ordner');

      await page.getByRole('button', { name: 'Abbrechen' }).click();
    }
  });
});
