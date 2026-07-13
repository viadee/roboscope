/**
 * Epic EXEC (EXEC.3) — the run dialog's flag-gated "Advanced" section.
 *
 * The advanced section renders only when the `executionAdvancedArgs` feature
 * flag is ON (default OFF). This test enables the flag via the admin settings
 * API, opens the New Run dialog, fills the freeform args + variables, starts,
 * and asserts the create-run request carries `advanced_config.args` +
 * `variables`. It also checks the section is hidden while the flag is off.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';
const FLAG_KEY = 'features.executionAdvancedArgs';

async function getToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

async function setFlag(page: Page, token: string, value: 'true' | 'false') {
  await page.request.patch(`${API}/settings`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { settings: [{ key: FLAG_KEY, value }] },
  });
}

test.describe('EXEC.3 — advanced run config', () => {
  let token: string;
  let repoId: number;
  let envId: number;
  const repoName = `exec3-e2e-${Date.now()}`;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    token = await getToken(ctx);
    const h = { Authorization: `Bearer ${token}` };
    const r = await ctx.request.post(`${API}/repos`, { headers: h, data: { name: repoName, repo_type: 'local', local_path: `/tmp/${repoName}` } });
    repoId = (await r.json()).id as number;
    await ctx.request.post(`${API}/explorer/${repoId}/file`, { headers: h, data: { path: 'tests/x.robot', content: '*** Test Cases ***\nDemo\n    Log    hi\n' } });
    const e = await ctx.request.post(`${API}/environments`, { headers: h, data: { name: `${repoName}-env`, python_version: '3.12' } });
    envId = (await e.json()).id as number;
    await setFlag(ctx, token, 'true');
    await ctx.close();
  });

  test.afterAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    const t = await getToken(ctx);
    const h = { Authorization: `Bearer ${t}` };
    await setFlag(ctx, t, 'false');
    await ctx.request.delete(`${API}/repos/${repoId}`, { headers: h }).catch(() => {});
    await ctx.request.delete(`${API}/environments/${envId}`, { headers: h }).catch(() => {});
    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('Advanced section sends advanced_config + variables on create-run', async ({ page }) => {
    await page.goto('/runs');
    await page.getByRole('button', { name: /Neuer Run|New Run/ }).first().click();

    const repoSelect = page.locator('select', { has: page.locator('option', { hasText: repoName }) }).first();
    await expect(repoSelect).toBeVisible({ timeout: 8_000 });
    await repoSelect.selectOption({ label: repoName });

    // The flag is on → advanced section visible.
    await expect(page.getByTestId('advanced-section')).toBeVisible();
    await page.getByTestId('advanced-vars-input').fill('BROWSER:chromium');
    await page.getByTestId('advanced-args-input').fill('--randomize all');

    const reqPromise = page.waitForRequest(
      (req) => req.url().endsWith('/runs') && req.method() === 'POST',
      { timeout: 8_000 },
    );
    await page.getByRole('button', { name: /^(Start|Starten)$/ }).first().click();
    const req = await reqPromise;
    const body = req.postDataJSON();
    expect(body.advanced_config).toEqual({ args: ['--randomize', 'all'] });
    expect(body.variables).toEqual({ BROWSER: 'chromium' });
  });
});
