/**
 * Capture screenshots for the RoboScope landing page.
 * Takes screenshots per language (en, de, fr, es) for each view.
 * Run: cd e2e && npx playwright test tests/take-screenshots.spec.ts
 */
import { test } from '@playwright/test';
import { loginViaApi } from '../helpers';
import path from 'path';

const SCREENSHOT_DIR = path.join(__dirname, '..', '..', '..', 'landing', 'screenshots');

const LANGUAGES = ['en', 'de', 'fr', 'es'] as const;

async function setLang(page: import('@playwright/test').Page, lang: string) {
  await page.evaluate((l) => localStorage.setItem('lang', l), lang);
}

async function loginWithLang(page: import('@playwright/test').Page, lang: string) {
  await loginViaApi(page);
  await setLang(page, lang);
  // Reload so the app picks up the new language
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
}

for (const lang of LANGUAGES) {
  test.describe(`Screenshots [${lang.toUpperCase()}]`, () => {
    test(`dashboard — ${lang}`, async ({ page }) => {
      await loginWithLang(page, lang);
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `dashboard-${lang}.png`),
      });
    });

    test(`explorer — ${lang}`, async ({ page }) => {
      await loginWithLang(page, lang);
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto('/repos');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);
      // Try to navigate to explorer via project card link
      const exploreLink = page.locator('a[href*="/explorer"]').first();
      if (await exploreLink.isVisible({ timeout: 3000 }).catch(() => false)) {
        await exploreLink.click();
      } else {
        await page.goto('/explorer');
      }
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `explorer-${lang}.png`),
      });
    });

    test(`execution — ${lang}`, async ({ page }) => {
      await loginWithLang(page, lang);
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto('/runs');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `execution-${lang}.png`),
      });
    });

    test(`stats — ${lang}`, async ({ page }) => {
      await loginWithLang(page, lang);
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto('/stats');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `stats-${lang}.png`),
      });
    });

    test(`ai — ${lang}`, async ({ page }) => {
      await loginWithLang(page, lang);
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto('/settings');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);
      // Click the AI & Generation tab
      const aiTab = page.locator('button.tab').last();
      await aiTab.click();
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `ai-${lang}.png`),
      });
    });
  });
}
