/**
 * Flow Editor — inline *** Variables *** + suite-level settings panels
 * (Story: Flow Editor — Verification & Hardening, AC-B).
 *
 * Verifies the new toolbar panels let an author define/edit/remove suite
 * variables and suite settings (Suite Setup/Teardown, Tags, Documentation,
 * Metadata) without leaving the Flow tab — closing the two-editors gap.
 * Serialization round-trip is pinned separately by the robotTextIO unit
 * tests; this exercises the live UI.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const SEED_ROBOT = `*** Settings ***
Library    Collections
Suite Setup    Log    booting

*** Variables ***
\${BASE_URL}    https://example.com
@{COLORS}    red    green

*** Test Cases ***
Demo Test
    Log    \${BASE_URL}
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  return (await res.json()).access_token as string;
}

async function createSeedRepo(page: Page, token: string): Promise<number> {
  const repoName = `flow-filesettings-e2e-${Date.now()}`;
  const localPath = `/tmp/roboscope-flow-filesettings-${Date.now()}`;
  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: repoName, repo_type: 'local', local_path: localPath },
  });
  expect(res.status()).toBe(201);
  const repoId = (await res.json()).id as number;
  await page.request.post(`${API}/explorer/${repoId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { path: 'tests/suite.robot', content: SEED_ROBOT },
  });
  return repoId;
}

async function openFlowEditor(page: Page, repoId: number) {
  await page.goto(`/explorer/${repoId}`);
  await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
  const testsFolder = page.locator('text=/^tests$/').first();
  await expect(testsFolder).toBeVisible({ timeout: 10_000 });
  const fileRow = page.locator('text=suite.robot').first();
  if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
  await expect(fileRow).toBeVisible({ timeout: 8_000 });
  await fileRow.click();
  const flowTab = page.locator('button', { hasText: /^Flow$/ }).first();
  await expect(flowTab).toBeVisible({ timeout: 8_000 });
  await flowTab.click();
  await expect(page.locator('.vue-flow__node[data-id$="-start"]').first()).toBeVisible({ timeout: 8_000 });
}

test.describe('Flow Editor — inline Variables + suite settings', () => {
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

  test('Variables panel lists existing suite variables and adds a new one', async ({ page }) => {
    await openFlowEditor(page, repoId);

    await page.getByTestId('flow-variables-toggle').click();
    const panel = page.getByTestId('flow-variables-panel');
    await expect(panel).toBeVisible();

    // Existing variables surface as editable name inputs.
    const names = panel.getByTestId('flow-variable-name');
    await expect(names).toHaveCount(2);
    await expect(names.nth(0)).toHaveValue('${BASE_URL}');

    // Add a new one (bare name auto-wraps to ${...}).
    await page.getByTestId('flow-variable-new-name').fill('TIMEOUT');
    await page.getByTestId('flow-variable-new-value').fill('30s');
    await page.getByTestId('flow-variable-add').click();

    await expect(panel.getByTestId('flow-variable-name')).toHaveCount(3);
    await expect(panel.getByTestId('flow-variable-name').nth(2)).toHaveValue('${TIMEOUT}');
  });

  test('Suite-settings panel lists existing settings and adds a new one', async ({ page }) => {
    await openFlowEditor(page, repoId);

    await page.getByTestId('flow-suite-settings-toggle').click();
    const panel = page.getByTestId('flow-suite-settings-panel');
    await expect(panel).toBeVisible();

    // The seeded "Suite Setup" is listed (Library is shown in its own panel).
    await expect(panel.getByText('Suite Setup', { exact: true })).toBeVisible();

    // Add "Suite Teardown" via the quick-add chip.
    const addChip = panel.getByTestId('flow-suite-setting-add').filter({ hasText: 'Suite Teardown' });
    await addChip.click();
    await expect(panel.getByText('Suite Teardown', { exact: true })).toBeVisible();
  });

  test('removing a variable updates the list', async ({ page }) => {
    await openFlowEditor(page, repoId);
    await page.getByTestId('flow-variables-toggle').click();
    const panel = page.getByTestId('flow-variables-panel');
    const before = await panel.getByTestId('flow-variable-name').count();
    await panel.getByTestId('flow-variable-remove').first().click();
    await expect(panel.getByTestId('flow-variable-name')).toHaveCount(before - 1);
  });
});
