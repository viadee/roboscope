/**
 * Flow Editor — [Template] data-driven rows table (Story FE-TPL).
 * A data-driven test renders its rows as an editable table node; adding a row
 * round-trips into the .robot via the Code tab.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const SEED_ROBOT = `*** Test Cases ***
Addition
    [Template]    Add Should Be
    1    2    3
    5    7    12
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

async function createSeedRepo(page: Page, token: string): Promise<number> {
  const repoName = `flow-tpl-e2e-${Date.now()}`;
  const localPath = `/tmp/roboscope-flow-tpl-${Date.now()}`;
  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: repoName, repo_type: 'local', local_path: localPath },
  });
  expect(res.status()).toBe(201);
  const repoId = (await res.json()).id as number;
  await page.request.post(`${API}/explorer/${repoId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { path: 'tests/tpl.robot', content: SEED_ROBOT },
  });
  return repoId;
}

async function openFlow(page: Page, repoId: number) {
  await page.goto(`/explorer/${repoId}`);
  await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
  const testsFolder = page.locator('text=/^tests$/').first();
  await expect(testsFolder).toBeVisible({ timeout: 10_000 });
  const fileRow = page.locator('text=tpl.robot').first();
  if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
  await expect(fileRow).toBeVisible({ timeout: 8_000 });
  await fileRow.click();
  const flowTab = page.locator('button', { hasText: /^Flow$/ }).first();
  await expect(flowTab).toBeVisible({ timeout: 8_000 });
  await flowTab.click();
  await expect(page.locator('.vue-flow__node[data-id$="-start"]').first()).toBeVisible({ timeout: 8_000 });
}

test.describe('Flow Editor — [Template] data table', () => {
  let token: string;
  let repoId: number;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    token = await getAuthToken(ctx);
    repoId = await createSeedRepo(ctx, token);
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

  test('renders the data table and adds a row that round-trips to code', async ({ page }) => {
    await openFlow(page, repoId);

    const table = page.getByTestId('flow-template-table');
    await expect(table).toBeVisible({ timeout: 8_000 });
    await expect(table.locator('tr')).toHaveCount(2);

    // Add a row. The controls live inside a vue-flow node on a transformed
    // canvas; dispatch the DOM click directly so the pane can't intercept it.
    await page.getByTestId('flow-template-add-row').dispatchEvent('click');
    await expect(table.locator('tr')).toHaveCount(3);
    const newRowCells = table.locator('tr').nth(2).getByTestId('flow-template-cell');
    await newRowCells.nth(0).fill('9');
    await newRowCells.nth(1).fill('1');
    await newRowCells.nth(2).fill('10');
    await newRowCells.nth(2).blur();

    // Round-trip via Code tab.
    const codeTab = page.locator('button', { hasText: /^Code$/ }).first();
    await codeTab.click();
    const code = page.locator('.cm-content');
    await expect(code).toBeVisible({ timeout: 8_000 });
    const text = await code.innerText();
    expect(text).toContain('[Template]    Add Should Be');
    expect(text).toContain('9');
    expect(text).toContain('10');
  });
});
