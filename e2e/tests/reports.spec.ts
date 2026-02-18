import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Reports Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should load reports page with heading', async ({ page }) => {
    await page.locator('.nav-item', { hasText: 'Reports' }).click();
    await page.waitForURL('**/reports');

    await expect(page.locator('h1', { hasText: 'Reports' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show reports table or empty state', async ({ page }) => {
    await page.goto('/reports');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h1', { hasText: 'Reports' })).toBeVisible({ timeout: 10_000 });

    // Either a data table with reports or empty state
    const hasTable = await page.locator('.data-table').isVisible().catch(() => false);
    const hasEmptyState = await page.getByText('Noch keine Reports vorhanden.').isVisible().catch(() => false);

    expect(hasTable || hasEmptyState).toBeTruthy();
  });
});
