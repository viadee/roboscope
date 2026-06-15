/**
 * Flow Editor — libdoc-per-environment is the universal keyword source
 * (Story FE-KWSRC). With the env-keywords endpoint serving a (mocked) libdoc
 * result, the palette shows those keywords — no rf-mcp, no static third-party.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const SEED_ROBOT = `*** Settings ***
Library    Browser

*** Test Cases ***
T
    Log    hi
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

let token: string;
let repoId: number;
let envId: number;

test.describe('Flow Editor — libdoc-sourced palette', () => {
  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    token = await getAuthToken(ctx);
    const auth = { Authorization: `Bearer ${token}` };
    const envRes = await ctx.request.post(`${API}/environments`, {
      headers: auth, data: { name: `libdoc-env-${Date.now()}`, python_version: '3.12' },
    });
    envId = (await envRes.json()).id;
    const repoRes = await ctx.request.post(`${API}/repos`, {
      headers: auth,
      data: {
        name: `flow-libdoc-e2e-${Date.now()}`,
        repo_type: 'local',
        local_path: `/tmp/roboscope-flow-libdoc-${Date.now()}`,
        environment_id: envId,
      },
    });
    repoId = (await repoRes.json()).id;
    await ctx.request.post(`${API}/explorer/${repoId}/file`, {
      headers: auth, data: { path: 'tests/lib.robot', content: SEED_ROBOT },
    });
    await ctx.close();
  });

  test.afterAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    const t = await getAuthToken(ctx);
    await ctx.request.delete(`${API}/repos/${repoId}`, { headers: { Authorization: `Bearer ${t}` } });
    await ctx.request.delete(`${API}/environments/${envId}`, { headers: { Authorization: `Bearer ${t}` } });
    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('palette shows libdoc keywords served by the env endpoint', async ({ page }) => {
    // Intercept the libdoc-per-environment endpoint with a distinctive keyword.
    await page.route('**/environments/*/keywords**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ready',
          source_hash: 'mock',
          updated_at: null,
          keywords: [
            { name: 'Libdoc Click Magic', library: 'Browser', args: ['selector'], shortdoc: 'from libdoc' },
          ],
        }),
      }),
    );

    await page.goto(`/explorer/${repoId}`);
    await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
    const testsFolder = page.locator('text=/^tests$/').first();
    await expect(testsFolder).toBeVisible({ timeout: 10_000 });
    const fileRow = page.locator('text=lib.robot').first();
    if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
    await fileRow.click();
    const flowTab = page.locator('button', { hasText: /^Flow$/ }).first();
    await expect(flowTab).toBeVisible({ timeout: 8_000 });
    await flowTab.click();

    const palette = page.locator('.keyword-palette');
    await expect(palette).toBeVisible({ timeout: 8_000 });
    await palette.locator('.palette-search').fill('Libdoc Click');
    await expect(palette.getByText('Libdoc Click Magic')).toBeVisible({ timeout: 6_000 });
  });
});
