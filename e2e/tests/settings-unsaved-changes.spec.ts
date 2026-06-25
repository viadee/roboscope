import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

/**
 * Settings → General: the sticky "unsaved changes" bar + dirty tracking +
 * leave guard. The General tab stacks many category cards above a single Save
 * button far below the fold, so the bar (pinned to the viewport) is the signal
 * that edits aren't persisted yet. Targets data-testids to stay locale-neutral.
 */
test.describe('Settings — unsaved changes bar', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.goto('/settings');
    await expect(page.locator('h1', { hasText: 'Einstellungen' })).toBeVisible({ timeout: 10_000 });
  });

  // The max_parallel_runs setting is a plain int input under the General tab.
  const row = (page) => page.locator('.setting-row', { hasText: 'max_parallel_runs' });
  const input = (page) => row(page).locator('input');

  test('bar appears on edit, shows the row marker, and discard reverts', async ({ page }) => {
    const original = await input(page).inputValue();

    // No changes yet → no bar.
    await expect(page.getByTestId('unsaved-bar')).toBeHidden();

    // Edit a setting → bar appears, row gets the dirty class, count is shown.
    await input(page).fill(String(Number(original) + 1));
    await expect(page.getByTestId('unsaved-bar')).toBeVisible();
    await expect(page.getByTestId('unsaved-count')).toContainText('1');
    await expect(row(page)).toHaveClass(/setting-row-dirty/);

    // Discard → bar gone, value restored, no persistence.
    await page.getByTestId('unsaved-discard').click();
    await expect(page.getByTestId('unsaved-bar')).toBeHidden();
    await expect(input(page)).toHaveValue(original);
    await expect(row(page)).not.toHaveClass(/setting-row-dirty/);
  });

  test('save persists and clears the bar', async ({ page }) => {
    const original = await input(page).inputValue();
    const changed = String(Number(original) + 1);

    await input(page).fill(changed);
    await expect(page.getByTestId('unsaved-bar')).toBeVisible();

    // Save via the sticky bar → bar clears (new baseline), value sticks.
    await page.getByTestId('unsaved-save').click();
    await expect(page.getByTestId('unsaved-bar')).toBeHidden();
    await expect(input(page)).toHaveValue(changed);

    // Reload proves persistence, then restore the original so the run is clean.
    await page.reload();
    await expect(input(page)).toHaveValue(changed, { timeout: 10_000 });
    await input(page).fill(original);
    await page.getByTestId('unsaved-save').click();
    await expect(page.getByTestId('unsaved-bar')).toBeHidden();
  });

  test('in-app navigation with unsaved changes prompts; dismiss keeps you on the page', async ({ page }) => {
    const original = await input(page).inputValue();
    await input(page).fill(String(Number(original) + 1));
    await expect(page.getByTestId('unsaved-bar')).toBeVisible();

    // The route-leave guard uses window.confirm; dismissing cancels navigation.
    let dialogSeen = false;
    page.once('dialog', (d) => {
      dialogSeen = d.type() === 'confirm';
      d.dismiss();
    });
    // Click the Dashboard sidebar link → in-app router navigation → guard fires.
    await page.locator('.nav-item', { hasText: 'Dashboard' }).first().click();

    // Guard prompted and we stayed put with the edit intact.
    await expect.poll(() => dialogSeen).toBe(true);
    await expect(page).toHaveURL(/\/settings/);
    await expect(page.getByTestId('unsaved-bar')).toBeVisible();

    // Accepting the prompt lets navigation through.
    page.once('dialog', (d) => d.accept());
    await page.locator('.nav-item', { hasText: 'Dashboard' }).first().click();
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
