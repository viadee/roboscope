/**
 * Epic GOV — deployment feature lockdown, exercised through the LIVE UI.
 *
 * Toggles the `features.packageManagement` flag via the settings API (DB
 * precedence — no backend restart needed), then drives the real Environments
 * page to confirm: when locked, the package-management controls are gone, a
 * "managed by your administrator" notice is shown, the package list still
 * renders read-only, and a direct API mutation is refused with 403. The flag
 * is always restored to ON in a finally / afterAll so the shared backend is
 * left in its default state.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';
const INSTALL_BTN = /Paket installieren/;

async function getToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

async function setPackageMgmt(page: Page, token: string, enabled: boolean) {
  const res = await page.request.patch(`${API}/settings`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { settings: [{ key: 'features.packageManagement', value: enabled ? 'true' : 'false' }] },
  });
  expect(res.ok()).toBeTruthy();
}

async function expandEnv(page: Page, name: string) {
  await page.goto('/environments');
  await expect(page.locator('h1', { hasText: 'Umgebungen' })).toBeVisible({ timeout: 10_000 });
  await page.locator('.card-header', { hasText: name }).first().click();
}

test.describe('GOV — package-management lockdown (live UI)', () => {
  let token: string;
  let envId: number;
  const envName = `gov-e2e-${Date.now()}`;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    token = await getToken(ctx);
    const res = await ctx.request.post(`${API}/environments`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: envName, python_version: '3.12' },
    });
    expect(res.status()).toBe(201);
    envId = (await res.json()).id as number;
    await ctx.close();
  });

  test.afterAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    const t = await getToken(ctx);
    await setPackageMgmt(ctx, t, true); // always restore default
    await ctx.request.delete(`${API}/environments/${envId}`, { headers: { Authorization: `Bearer ${t}` } });
    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('default (enabled): install control is visible', async ({ page }) => {
    await setPackageMgmt(page, await getToken(page), true);
    await expandEnv(page, envName);
    await expect(page.getByRole('button', { name: INSTALL_BTN })).toBeVisible({ timeout: 8_000 });
    await expect(page.locator('.pkg-managed-notice')).toHaveCount(0);
  });

  test('locked (disabled): controls hidden, notice shown, API mutation 403', async ({ page }) => {
    const t = await getToken(page);
    await setPackageMgmt(page, t, false);
    try {
      await expandEnv(page, envName);
      // Read-only notice present, mutating controls gone.
      await expect(page.locator('.pkg-managed-notice')).toBeVisible({ timeout: 8_000 });
      await expect(page.getByRole('button', { name: INSTALL_BTN })).toHaveCount(0);
      // Server enforcement: a direct API mutation is refused even for admin.
      const resp = await page.request.post(`${API}/environments/${envId}/packages`, {
        headers: { Authorization: `Bearer ${t}` },
        data: { name: 'robotframework' },
      });
      expect(resp.status()).toBe(403);
      expect(JSON.stringify(await resp.json())).toContain('feature_disabled:packageManagement');
    } finally {
      await setPackageMgmt(page, t, true); // restore promptly even if an assertion fails
    }
  });
});
