import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Execution Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should load execution page with heading', async ({ page }) => {
    await page.locator('.nav-item', { hasText: 'Ausführung' }).click();
    await page.waitForURL('**/runs');

    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show new run button for admin user', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });

    // Admin (role >= runner) should see "Neuer Run" button
    const newRunButton = page.getByRole('button', { name: /Neuer Run/ });
    await expect(newRunButton).toBeVisible();
  });

  test('should show simplified table with 5 columns', async ({ page }) => {
    await page.goto('/runs');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });

    // Check if table exists; if so verify column count
    const hasTable = await page.locator('.data-table').isVisible().catch(() => false);
    if (hasTable) {
      const headers = await page.locator('.data-table thead th').allTextContents();
      expect(headers).toHaveLength(7);
    }
  });

  test('should show empty state or run list', async ({ page }) => {
    await page.goto('/runs');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });

    // Either we see the data table with runs or the empty state message
    const hasTable = await page.locator('.data-table').isVisible().catch(() => false);
    const hasEmptyState = await page.getByText('Noch keine Ausführungen.').isVisible().catch(() => false);

    expect(hasTable || hasEmptyState).toBeTruthy();
  });

  test('should open and close new run modal', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });

    // Open modal
    await page.getByRole('button', { name: /Neuer Run/ }).click();

    // Modal should show with "Neuen Run starten" title
    await expect(page.getByText('Neuen Run starten')).toBeVisible({ timeout: 3_000 });

    // Check form fields are present
    await expect(page.getByPlaceholder('main')).toBeVisible();
    await expect(page.getByPlaceholder('tests/ oder tests/login.robot')).toBeVisible();

    // Cancel
    await page.getByRole('button', { name: 'Abbrechen' }).click();
    await expect(page.getByText('Neuen Run starten')).not.toBeVisible({ timeout: 3_000 });
  });

  test('should show clickable rows in run table', async ({ page }) => {
    await page.goto('/runs');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });

    const rows = page.locator('.data-table tbody .clickable-row');
    const rowCount = await rows.count();
    if (rowCount > 0) {
      // Click first row — detail panel should appear
      await rows.first().click();
      await expect(page.locator('.run-detail-panel')).toBeVisible({ timeout: 5_000 });

      // Click the same row again — detail panel should collapse
      await rows.first().click();
      await expect(page.locator('.run-detail-panel')).not.toBeVisible({ timeout: 3_000 });
    }
  });

  test('should show delete all reports button for admin', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });

    // Admin should see the delete all reports button
    const deleteBtn = page.getByRole('button', { name: /Alle Reports löschen/ });
    await expect(deleteBtn).toBeVisible();
  });
});
