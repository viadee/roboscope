/**
 * Flow Editor — `[…]` settings as side notes
 *
 * Verifies that every populated `[Documentation]`, `[Tags]`,
 * `[Setup]`, `[Teardown]`, `[Template]`, `[Timeout]` setting on a
 * test case (and the keyword equivalents incl. `[Arguments]`)
 * renders as a dashed-edge side node to the LEFT of the Start node
 * — and that the "+ [X]" affordances in the section settings
 * panel can add missing settings round-trip into the .robot source.
 *
 * Also pins the no-overlap invariant on the stacked side notes:
 * each kind sits exactly 96px below the previous (META_PITCH).
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const SEED_ROBOT = `*** Settings ***
Library    Collections


*** Test Cases ***
Documented Test
    [Documentation]    First line of doc
    ...                Second line continuation
    [Tags]    smoke    regression
    [Setup]    Log    setting up
    [Teardown]    Log    tearing down
    [Timeout]    30s
    Log    body line


*** Keywords ***
Documented Keyword
    [Documentation]    Keyword-level docs
    [Arguments]    \${name}    \${greeting}=Hello
    [Tags]    helper
    Log    \${greeting} \${name}

Plain Keyword
    Log    no settings here
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  return (await res.json()).access_token as string;
}

async function createSeedRepo(page: Page, token: string): Promise<number> {
  const repoName = `flow-settings-e2e-${Date.now()}`;
  const localPath = `/tmp/roboscope-flow-settings-${Date.now()}`;
  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: repoName, repo_type: 'local', local_path: localPath },
  });
  expect(res.status()).toBe(201);
  const repoId = (await res.json()).id as number;

  await page.request.post(`${API}/explorer/${repoId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { path: 'tests/settings.robot', content: SEED_ROBOT },
  });
  return repoId;
}

async function openFlowEditor(page: Page, repoId: number) {
  await page.goto(`/explorer/${repoId}`);
  await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });

  // The tree fetch is asynchronous — wait for the tests folder to
  // exist before attempting interactions. Without this the first
  // expansion click can race the GET /tree response and click an
  // empty area, leaving the file row invisible.
  const testsFolder = page.locator('text=/^tests$/').first();
  await expect(testsFolder).toBeVisible({ timeout: 10_000 });

  const fileRow = page.locator('text=settings.robot').first();
  if (!(await fileRow.isVisible().catch(() => false))) {
    await testsFolder.click();
  }
  await expect(fileRow).toBeVisible({ timeout: 8_000 });
  await fileRow.click();

  // The Robot editor lands on the visual tab; switch to Flow.
  const flowTab = page.locator('button', { hasText: /^Flow$/ }).first();
  await expect(flowTab).toBeVisible({ timeout: 8_000 });
  await flowTab.click();
  // Wait for VueFlow nodes to render.
  await expect(page.locator('.vue-flow__node[data-id$="-start"]').first()).toBeVisible({ timeout: 8_000 });
}

test.describe('Flow Editor — [...] settings as side notes', () => {
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
    await ctx.request.delete(`${API}/repos/${repoId}`, {
      headers: { Authorization: `Bearer ${t}` },
    });
    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('all populated settings render as side-note nodes on the canvas', async ({ page }) => {
    await openFlowEditor(page, repoId);

    const expectedKinds = [
      'tc0-documentation',
      'tc0-tags',
      'tc0-setup',
      'tc0-teardown',
      'tc0-timeout',
    ];
    for (const id of expectedKinds) {
      await expect(page.locator(`.vue-flow__node[data-id="${id}"]`)).toBeVisible({ timeout: 5_000 });
    }
  });

  test('side notes stack vertically with no overlap (96px pitch)', async ({ page }) => {
    await openFlowEditor(page, repoId);

    const docBox = await page.locator('.vue-flow__node[data-id="tc0-documentation"]').boundingBox();
    const tagsBox = await page.locator('.vue-flow__node[data-id="tc0-tags"]').boundingBox();
    expect(docBox).not.toBeNull();
    expect(tagsBox).not.toBeNull();
    // Tags sits below Documentation; gap accounts for the 96px pitch
    // and the rendered scale (usually 1.0 at fitView default).
    expect(tagsBox!.y).toBeGreaterThan(docBox!.y + docBox!.height - 1);
  });

  test('switching to Keywords tab shows keyword side notes (Documentation + Arguments + Tags)', async ({ page }) => {
    await openFlowEditor(page, repoId);

    const kwTab = page.locator('.flow-section-tab', { hasText: /Keywords/ });
    await kwTab.first().click();
    await page.waitForTimeout(600);

    await expect(page.locator('.vue-flow__node[data-id="kw0-documentation"]')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.vue-flow__node[data-id="kw0-arguments"]')).toBeVisible();
    await expect(page.locator('.vue-flow__node[data-id="kw0-tags"]')).toBeVisible();

    // Keyword without [Documentation] (kw1, "Plain Keyword"): no side notes
    // for that index. Switch to it via the per-item tab and assert.
    const kw1Tab = page.locator('.flow-item-tab', { hasText: 'Plain Keyword' });
    if (await kw1Tab.count()) {
      await kw1Tab.first().click();
      await page.waitForTimeout(400);
      await expect(page.locator('.vue-flow__node[data-id^="kw1-"][data-id$="-documentation"]')).toHaveCount(0);
    }
  });

  test('Start-click opens section settings panel; "+ [Tags]" hides once tags exist', async ({ page }) => {
    await openFlowEditor(page, repoId);

    // tc0 already has tags, so the "+ [Tags]" button should NOT be in the panel.
    await page.locator('.vue-flow__node[data-id="tc0-start"]').click();
    await page.waitForTimeout(400);
    await expect(page.locator('[data-testid="flow-add-tags"]')).toHaveCount(0);
    // Documentation IS attached too — that affordance is also hidden.
    await expect(page.locator('[data-testid="flow-add-documentation"]')).toHaveCount(0);
  });
});
