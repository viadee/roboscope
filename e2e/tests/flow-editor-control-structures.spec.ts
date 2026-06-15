/**
 * Flow Editor — nested control structures render + round-trip in the LIVE app
 * (Story: Flow Editor — Verification & Hardening, AC-D2).
 *
 * Loads a suite with nested FOR/IF/TRY into the Flow tab, confirms the canvas
 * renders, then switches to the Code tab and asserts the nested structure +
 * matching ENDs survived the text→form→graph→form→text round-trip intact.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const SEED_ROBOT = `*** Test Cases ***
Nested Control
    IF    \${cond}
        FOR    \${i}    IN RANGE    3
            Log    \${i}
        END
    ELSE
        Log    nope
    END
    TRY
        Do Thing
    EXCEPT    Boom    AS    \${err}
        Log    \${err}
    FINALLY
        Cleanup
    END
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  return (await res.json()).access_token as string;
}

async function createSeedRepo(page: Page, token: string): Promise<number> {
  const repoName = `flow-control-e2e-${Date.now()}`;
  const localPath = `/tmp/roboscope-flow-control-${Date.now()}`;
  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: repoName, repo_type: 'local', local_path: localPath },
  });
  expect(res.status()).toBe(201);
  const repoId = (await res.json()).id as number;
  await page.request.post(`${API}/explorer/${repoId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { path: 'tests/control.robot', content: SEED_ROBOT },
  });
  return repoId;
}

async function openFile(page: Page, repoId: number) {
  await page.goto(`/explorer/${repoId}`);
  await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
  const testsFolder = page.locator('text=/^tests$/').first();
  await expect(testsFolder).toBeVisible({ timeout: 10_000 });
  const fileRow = page.locator('text=control.robot').first();
  if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
  await expect(fileRow).toBeVisible({ timeout: 8_000 });
  await fileRow.click();
}

test.describe('Flow Editor — nested control structures', () => {
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

  test('renders the flow and preserves nesting on a flow→code round-trip', async ({ page }) => {
    await openFile(page, repoId);

    // Flow tab renders the canvas.
    const flowTab = page.locator('button', { hasText: /^Flow$/ }).first();
    await expect(flowTab).toBeVisible({ timeout: 8_000 });
    await flowTab.click();
    await expect(page.locator('.vue-flow__node[data-id$="-start"]').first()).toBeVisible({ timeout: 8_000 });

    // Switch to Code — RobotEditor serializes the form back to .robot text.
    const codeTab = page.locator('button', { hasText: /^Code$/ }).first();
    await expect(codeTab).toBeVisible({ timeout: 8_000 });
    await codeTab.click();

    const code = page.locator('.cm-content');
    await expect(code).toBeVisible({ timeout: 8_000 });
    const text = (await code.innerText()).replace(/ /g, ' ');

    // Structure + matching ENDs conserved.
    expect(text).toContain('IF');
    expect(text).toContain('FOR');
    expect(text).toContain('ELSE');
    expect(text).toContain('TRY');
    expect(text).toContain('EXCEPT');
    expect(text).toContain('FINALLY');
    expect(text).toContain('${err}');
    expect((text.match(/\bEND\b/g) || []).length).toBe(3);
  });
});
