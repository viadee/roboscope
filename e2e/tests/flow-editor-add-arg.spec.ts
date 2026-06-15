/**
 * Flow Editor — "+ Add argument" custom value (Story EDITOR-9b).
 * The custom-value field lets the author type the exact cell (a bare value or
 * name=value) instead of only appending the next positional parameter; it
 * round-trips into the .robot via the Code tab.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const SEED_ROBOT = `*** Test Cases ***
T
    Log    hello
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

let token: string;
let repoId: number;

test.describe('Flow Editor — add custom argument', () => {
  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    token = await getAuthToken(ctx);
    const res = await ctx.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: `flow-addarg-e2e-${Date.now()}`, repo_type: 'local', local_path: `/tmp/roboscope-flow-addarg-${Date.now()}` },
    });
    repoId = (await res.json()).id;
    await ctx.request.post(`${API}/explorer/${repoId}/file`, {
      headers: { Authorization: `Bearer ${token}` }, data: { path: 'tests/argpick.robot', content: SEED_ROBOT },
    });
    await ctx.close();
  });

  test.afterAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    const t = await getAuthToken(ctx);
    await ctx.request.delete(`${API}/repos/${repoId}`, { headers: { Authorization: `Bearer ${t}` } });
    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('typing a custom name=value adds it verbatim and round-trips', async ({ page }) => {
    await page.goto(`/explorer/${repoId}`);
    await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
    const testsFolder = page.locator('text=/^tests$/').first();
    await expect(testsFolder).toBeVisible({ timeout: 10_000 });
    const fileRow = page.locator('text=argpick.robot').first();
    if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
    await fileRow.click();
    const flowTab = page.locator('button', { hasText: /^Flow$/ }).first();
    await flowTab.click();
    await expect(page.locator('.vue-flow__node[data-id$="-start"]').first()).toBeVisible({ timeout: 8_000 });

    // Select the Log keyword node → detail panel opens.
    await page.locator('.vue-flow__node', { hasText: 'Log' }).first().click();

    // Open the "+ Add argument" picker and type a custom named value.
    await page.locator('.flow-add-arg-wrap button').first().click();
    const input = page.getByTestId('add-arg-custom-input');
    await expect(input).toBeVisible({ timeout: 5_000 });
    await input.fill('level=DEBUG');
    await page.getByTestId('add-arg-custom-add').click();

    // Round-trip via Code tab keeps the exact cell.
    await page.locator('button', { hasText: /^Code$/ }).first().click();
    const code = page.locator('.cm-content');
    await expect(code).toBeVisible({ timeout: 8_000 });
    expect(await code.innerText()).toContain('level=DEBUG');
  });
});
