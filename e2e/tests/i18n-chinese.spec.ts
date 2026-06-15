/**
 * Chinese (zh) locale — switching to 中文 renders Chinese UI.
 * (Goal: add Chinese locale support.)
 */
import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('i18n — Chinese locale', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('ZH language button switches the UI to Chinese', async ({ page }) => {
    // The language switcher offers ZH alongside DE/EN/FR/ES.
    const zhBtn = page.locator('.lang-btn', { hasText: 'ZH' });
    await expect(zhBtn).toBeVisible({ timeout: 10_000 });
    await zhBtn.click();

    // Active state + persisted preference.
    await expect(zhBtn).toHaveClass(/active/);
    expect(await page.evaluate(() => localStorage.getItem('lang'))).toBe('zh');

    // Navigation renders in Chinese (nav.dashboard / nav.execution).
    await expect(page.getByText('仪表盘').first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('执行').first()).toBeVisible();
  });

  test('Chinese persists across reload', async ({ page }) => {
    await page.locator('.lang-btn', { hasText: 'ZH' }).click();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('.lang-btn', { hasText: 'ZH' })).toHaveClass(/active/, { timeout: 10_000 });
    await expect(page.getByText('仪表盘').first()).toBeVisible({ timeout: 5_000 });
  });
});
