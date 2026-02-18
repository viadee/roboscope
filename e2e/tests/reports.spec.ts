import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Reports (merged into Execution page)', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should not have a Reports nav item in sidebar', async ({ page }) => {
    const labels = await page.locator('.nav-label').allTextContents();
    expect(labels).not.toContain('Reports');
  });

  test('should show execution page when navigating to /runs', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });
  });
});
