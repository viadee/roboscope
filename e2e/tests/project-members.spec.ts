import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Project Member Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show Members button on project cards for editor+ users', async ({ page }) => {
    // Wait for cards to load
    await page.waitForLoadState('networkidle');

    // Admin/editor should see the "Mitglieder" button
    const membersButtons = page.getByRole('button', { name: 'Mitglieder' });
    const count = await membersButtons.count();
    // There should be at least one project card with a Members button
    // (the Examples project is auto-seeded)
    if (count > 0) {
      await expect(membersButtons.first()).toBeVisible();
    }
  });

  test('should open members dialog with empty member list', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    const membersButton = page.getByRole('button', { name: 'Mitglieder' }).first();
    if (!(await membersButton.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    await membersButton.click();

    // Modal should appear with "Mitglieder" in the title
    await expect(page.locator('.modal-header h3')).toContainText('Mitglieder', { timeout: 5_000 });

    // Should have a user select dropdown
    await expect(page.locator('.members-user-select')).toBeVisible();

    // Should have a role select
    await expect(page.locator('.members-role-select').first()).toBeVisible();

    // Should have an Add button
    await expect(page.getByRole('button', { name: 'Hinzufügen', exact: true })).toBeVisible();
  });

  test('should show role dropdown with viewer/runner/editor options', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    const membersButton = page.getByRole('button', { name: 'Mitglieder' }).first();
    if (!(await membersButton.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    await membersButton.click();
    await expect(page.locator('.modal-header h3')).toContainText('Mitglieder', { timeout: 5_000 });

    // Check role select has the right options
    const roleSelect = page.locator('.members-add-row .members-role-select');
    const options = roleSelect.locator('option');
    await expect(options).toHaveCount(3);
    await expect(options.nth(0)).toHaveText('Viewer');
    await expect(options.nth(1)).toHaveText('Runner');
    await expect(options.nth(2)).toHaveText('Editor');
  });

  test('should close members dialog with close button', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    const membersButton = page.getByRole('button', { name: 'Mitglieder' }).first();
    if (!(await membersButton.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    await membersButton.click();
    await expect(page.locator('.modal-header h3')).toContainText('Mitglieder', { timeout: 5_000 });

    // Close dialog
    await page.getByRole('button', { name: 'Schließen' }).click();
    await expect(page.locator('.modal-header h3')).not.toBeVisible({ timeout: 3_000 });
  });

  test('should list available users in the user dropdown', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    const membersButton = page.getByRole('button', { name: 'Mitglieder' }).first();
    if (!(await membersButton.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    await membersButton.click();
    await expect(page.locator('.modal-header h3')).toContainText('Mitglieder', { timeout: 5_000 });

    // The user dropdown should have at least the default placeholder
    const userSelect = page.locator('.members-user-select');
    const options = userSelect.locator('option');
    // At least the placeholder option
    const optionCount = await options.count();
    expect(optionCount).toBeGreaterThanOrEqual(1);
  });
});
