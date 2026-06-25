/**
 * Epic EXEC (EXEC-1/EXEC-3) — the run dialog now exposes Include/Exclude tags,
 * which the backend runner already turns into `robot --include/--exclude`.
 * Real UI: open the New Run dialog, set an include tag, start, and assert the
 * create-run request carries `tags_include` (proving the dialog → backend wire;
 * the runner application is already covered by backend tests).
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

async function getToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

test.describe('EXEC — run dialog passes tags', () => {
  let token: string;
  let repoId: number;
  let envId: number;
  const repoName = `exec-e2e-${Date.now()}`;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    token = await getToken(ctx);
    const h = { Authorization: `Bearer ${token}` };
    const r = await ctx.request.post(`${API}/repos`, { headers: h, data: { name: repoName, repo_type: 'local', local_path: `/tmp/${repoName}` } });
    repoId = (await r.json()).id as number;
    await ctx.request.post(`${API}/explorer/${repoId}/file`, { headers: h, data: { path: 'tests/x.robot', content: '*** Test Cases ***\nDemo\n    [Tags]    smoke\n    Log    hi\n' } });
    // An environment must exist so the dialog doesn't divert to the "set up env" prompt.
    const e = await ctx.request.post(`${API}/environments`, { headers: h, data: { name: `${repoName}-env`, python_version: '3.12' } });
    envId = (await e.json()).id as number;
    await ctx.close();
  });

  test.afterAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    const t = await getToken(ctx);
    const h = { Authorization: `Bearer ${t}` };
    await ctx.request.delete(`${API}/repos/${repoId}`, { headers: h }).catch(() => {});
    await ctx.request.delete(`${API}/environments/${envId}`, { headers: h }).catch(() => {});
    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('Include tags are sent on the create-run request', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.getByRole('button', { name: /Neuer Run|New Run/ })).toBeVisible({ timeout: 10_000 });

    await page.getByRole('button', { name: /Neuer Run|New Run/ }).first().click();

    // Repo select carries the "please select" placeholder option.
    const repoSelect = page.locator('select', { has: page.locator('option', { hasText: repoName }) }).first();
    await expect(repoSelect).toBeVisible({ timeout: 8_000 });
    await repoSelect.selectOption({ label: repoName });

    await page.getByPlaceholder('smoke, regression').first().fill('smoke');

    const reqPromise = page.waitForRequest(
      (req) => req.url().endsWith('/runs') && req.method() === 'POST',
      { timeout: 8_000 },
    );
    await page.getByRole('button', { name: /^(Start|Starten)$/ }).first().click();
    const req = await reqPromise;
    expect(req.postDataJSON().tags_include).toBe('smoke');
  });
});
