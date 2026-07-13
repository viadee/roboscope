/**
 * First-Start Experience — the "learning curve" journey.
 *
 * Covers the onboarding gap from the use-case audit (2026-07-02):
 *  - a FRESH user's very first login must land on /welcome (Story 4-2),
 *    show the why-you-have-access explanation and be dismissible,
 *  - the dismissal must persist (no re-redirect on the next navigation),
 *  - the tour trigger must be discoverable in the header,
 *  - the in-app docs must be reachable, sectioned and searchable.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const ADMIN_EMAIL = 'admin@roboscope.local';
const ADMIN_PASSWORD = 'admin123';

async function getAdminToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  });
  return (await res.json()).access_token as string;
}

test.describe.serial('First-Start Experience — Welcome / Tour / Docs', () => {
  const stamp = Date.now();
  const freshEmail = `first-start-${stamp}@test.local`;
  const freshUsername = `first-start-${stamp}`;
  const freshPassword = 'test123456';
  let freshUserId: number | undefined;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    const token = await getAdminToken(page);
    const res = await page.request.post(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { email: freshEmail, username: freshUsername, password: freshPassword, role: 'editor' },
    });
    expect(res.status()).toBeLessThan(300);
    freshUserId = (await res.json()).id as number;
    await page.close();
  });

  test.afterAll(async ({ browser }) => {
    if (!freshUserId) return;
    const page = await browser.newPage();
    const token = await getAdminToken(page);
    await page.request.delete(`${API}/auth/users/${freshUserId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    await page.close();
  });

  test('fresh user is redirected to /welcome, sees why-access and can dismiss it durably', async ({ page }) => {
    // Deliberately do NOT use the helpers here — they clear the
    // first-login flag, which is exactly what this test is about.
    await page.goto('/login');
    await page.getByPlaceholder('admin@roboscope.local').fill(freshEmail);
    await page.getByPlaceholder('Passwort').fill(freshPassword);
    await page.getByRole('button', { name: 'Anmelden' }).click();

    // Router intercept (Story 4-2): first_login_complete === false → /welcome
    await expect(page).toHaveURL(/\/welcome/, { timeout: 15_000 });
    await expect(page.locator('#welcome-heading')).toBeVisible();
    // Why-you-have-access explanation (team / project / no-access variant)
    await expect(page.locator('.welcome-why')).toBeVisible();
    // At least one CTA must be offered
    await expect(page.locator('.welcome-cta').first()).toBeVisible();

    // Dismiss via the skip link → dashboard
    await page.locator('.welcome-skip').click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });

    // Dismissal is persisted server-side: a later navigation must NOT
    // bounce back to /welcome.
    await page.goto('/repos');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/\/welcome/);
  });

  test('tour trigger is discoverable in the app header', async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(
      page.getByRole('button', { name: 'Tutorial starten' }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('docs page shows TOC, sections and a working search', async ({ page }) => {
    await loginAndGoToDashboard(page);
    await page.goto('/docs');
    await expect(page.locator('h1', { hasText: 'Dokumentation' })).toBeVisible({ timeout: 10_000 });

    // TOC + a healthy number of sections (docs content loads async per locale)
    await expect(page.locator('.docs-toc')).toBeVisible();
    const sections = page.locator('.doc-section');
    await expect(sections.first()).toBeVisible({ timeout: 10_000 });
    expect(await sections.count()).toBeGreaterThanOrEqual(3);

    // Search: a nonsense term empties the list, clearing restores it
    const search = page.getByPlaceholder('Dokumentation durchsuchen...');
    await expect(search).toBeVisible();
    await search.fill('xyzzy-kein-treffer-42');
    await expect(page.locator('.docs-empty')).toBeVisible({ timeout: 5_000 });
    await search.fill('');
    expect(await page.locator('.doc-section').count()).toBeGreaterThanOrEqual(3);

    // TOC navigation: clicking the first section entry keeps content visible
    await page.locator('.docs-toc a, .docs-toc button').first().click();
    await expect(page.locator('.section-heading').first()).toBeVisible();
  });
});
