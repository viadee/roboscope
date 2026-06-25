/**
 * Epic RES — inserting a keyword from a repo `.resource` file auto-adds the
 * matching `Resource` import, so the keyword actually resolves at runtime
 * (Daniel's "make local/repository resources usable"). Real UI: seed a
 * resource + a test file, open the test in the Flow editor, insert the
 * resource keyword from the palette, and assert the generated `.robot`
 * (Code tab) carries `Resource    ../resources/common.resource` + the call.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const RESOURCE = `*** Keywords ***
My Shared Keyword
    Log    shared
`;
const TEST_FILE = `*** Test Cases ***
Uses It
    Log    hi
`;

async function getToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

test.describe('RES — Resource auto-import on keyword insert', () => {
  let token: string;
  let repoId: number;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    token = await getToken(ctx);
    const stamp = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    const res = await ctx.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: `res-e2e-${stamp}`, repo_type: 'local', local_path: `/tmp/roboscope-res-${stamp}` },
    });
    expect(res.status()).toBe(201);
    repoId = (await res.json()).id as number;
    const h = { Authorization: `Bearer ${token}` };
    await ctx.request.post(`${API}/explorer/${repoId}/file`, { headers: h, data: { path: 'resources/common.resource', content: RESOURCE } });
    await ctx.request.post(`${API}/explorer/${repoId}/file`, { headers: h, data: { path: 'tests/uses_resource.robot', content: TEST_FILE } });
    await ctx.close();
  });

  test.afterAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    const t = await getToken(ctx);
    await ctx.request.delete(`${API}/repos/${repoId}`, { headers: { Authorization: `Bearer ${t}` } }).catch(() => {});
    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('inserting a .resource keyword adds the Resource import', async ({ page }) => {
    await page.goto(`/explorer/${repoId}`);
    await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
    const testsFolder = page.locator('text=/^tests$/').first();
    await expect(testsFolder).toBeVisible({ timeout: 10_000 });
    const fileRow = page.locator('text=uses_resource.robot').first();
    if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
    await expect(fileRow).toBeVisible({ timeout: 8_000 });
    await fileRow.click();

    // Flow tab
    await page.locator('button', { hasText: /^Flow$/ }).first().click();
    await expect(page.locator('.vue-flow__node[data-id$="-start"]').first()).toBeVisible({ timeout: 8_000 });

    // Open the "Project: common.resource" palette category, select the keyword, add it.
    const palette = page.locator('.keyword-palette');
    const projHeader = palette.locator('.category-header', { hasText: 'common.resource' }).first();
    await expect(projHeader).toBeVisible({ timeout: 8_000 });
    if (!(await palette.getByText('My Shared Keyword', { exact: true }).first().isVisible().catch(() => false))) {
      await projHeader.click();
    }
    await palette.getByText('My Shared Keyword', { exact: true }).first().click();
    await palette.locator('.palette-add-btn').click();

    // Code tab — the import + call must be present.
    await page.locator('button', { hasText: /^Code$/ }).first().click();
    const code = page.locator('.cm-content');
    await expect(code).toBeVisible({ timeout: 8_000 });
    const text = (await code.innerText()).replace(/ /g, ' ');
    expect(text).toContain('My Shared Keyword');
    expect(text).toMatch(/Resource\s+\.\.\/resources\/common\.resource/);
  });
});
