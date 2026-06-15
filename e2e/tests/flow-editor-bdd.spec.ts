/**
 * Flow Editor — Gherkin/BDD prefix awareness (Story FE-BDD).
 * A BDD suite renders prefix badges on the steps and the Given/When/Then
 * prefixes survive a flow→code round-trip verbatim.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const SEED_ROBOT = `*** Test Cases ***
BDD Flow
    Given a user exists
    When the user logs in
    Then the dashboard is shown
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

async function createSeedRepo(page: Page, token: string): Promise<number> {
  const repoName = `flow-bdd-e2e-${Date.now()}`;
  const localPath = `/tmp/roboscope-flow-bdd-${Date.now()}`;
  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: repoName, repo_type: 'local', local_path: localPath },
  });
  expect(res.status()).toBe(201);
  const repoId = (await res.json()).id as number;
  await page.request.post(`${API}/explorer/${repoId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { path: 'tests/bdd.robot', content: SEED_ROBOT },
  });
  return repoId;
}

async function openFile(page: Page, repoId: number) {
  await page.goto(`/explorer/${repoId}`);
  await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
  const testsFolder = page.locator('text=/^tests$/').first();
  await expect(testsFolder).toBeVisible({ timeout: 10_000 });
  const fileRow = page.locator('text=bdd.robot').first();
  if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
  await expect(fileRow).toBeVisible({ timeout: 8_000 });
  await fileRow.click();
}

test.describe('Flow Editor — BDD prefix awareness', () => {
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

  test('renders prefix badges and round-trips Given/When/Then', async ({ page }) => {
    await openFile(page, repoId);

    const flowTab = page.locator('button', { hasText: /^Flow$/ }).first();
    await expect(flowTab).toBeVisible({ timeout: 8_000 });
    await flowTab.click();
    await expect(page.locator('.vue-flow__node[data-id$="-start"]').first()).toBeVisible({ timeout: 8_000 });

    // Three BDD badges (Given / When / Then).
    await expect(page.getByTestId('bdd-badge')).toHaveCount(3);
    await expect(page.getByTestId('bdd-badge').nth(0)).toHaveText('Given');

    // Round-trip via Code tab keeps the prefixes verbatim.
    const codeTab = page.locator('button', { hasText: /^Code$/ }).first();
    await codeTab.click();
    const code = page.locator('.cm-content');
    await expect(code).toBeVisible({ timeout: 8_000 });
    const text = await code.innerText();
    expect(text).toContain('Given a user exists');
    expect(text).toContain('When the user logs in');
    expect(text).toContain('Then the dashboard is shown');
  });
});
