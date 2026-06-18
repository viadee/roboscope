/**
 * UX waves D1–D6 (ux-flow-editor-resources.md) — the Flow Editor custom-resource
 * experience. Real UI: seed a `.resource` file whose keyword declares a required
 * argument, open a test in the Flow editor, and assert:
 *   D1 — the pinned "Your resources" section renders (separate from libraries).
 *   D5/D6 — the sort + filter controls are present in the palette header.
 *   D2 — inserting the resource keyword shows an import-confirmation toast.
 *   D3 — the inserted node opens with its required argument slot pre-filled.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

// A resource keyword with a REQUIRED argument (drives the D3 pre-fill check),
// plus a second keyword so the file is more than a one-liner.
const RESOURCE = `*** Keywords ***
Open Login Page
    [Arguments]    \${url}
    Log    \${url}

Submit Credentials
    Log    submitted
`;
const TEST_FILE = `*** Test Cases ***
Logs In
    Log    start
`;

async function getToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

test.describe('Flow Editor — custom-resource UX (D1–D6)', () => {
  let token: string;
  let repoId: number;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newPage();
    token = await getToken(ctx);
    const stamp = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    const res = await ctx.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: `res-ux-e2e-${stamp}`, repo_type: 'local', local_path: `/tmp/roboscope-res-ux-${stamp}` },
    });
    expect(res.status()).toBe(201);
    repoId = (await res.json()).id as number;
    const h = { Authorization: `Bearer ${token}` };
    await ctx.request.post(`${API}/explorer/${repoId}/file`, { headers: h, data: { path: 'resources/login.resource', content: RESOURCE } });
    await ctx.request.post(`${API}/explorer/${repoId}/file`, { headers: h, data: { path: 'tests/login_test.robot', content: TEST_FILE } });
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

  test('resources section, sort/filter controls, import toast, and arg pre-fill', async ({ page }) => {
    await page.goto(`/explorer/${repoId}`);
    await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
    const testsFolder = page.locator('text=/^tests$/').first();
    await expect(testsFolder).toBeVisible({ timeout: 10_000 });
    const fileRow = page.locator('text=login_test.robot').first();
    if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
    await expect(fileRow).toBeVisible({ timeout: 8_000 });
    await fileRow.click();

    // Flow tab
    await page.locator('button', { hasText: /^Flow$/ }).first().click();
    await expect(page.locator('.vue-flow__node[data-id$="-start"]').first()).toBeVisible({ timeout: 8_000 });

    const palette = page.locator('.keyword-palette');

    // D1 — the pinned "Your resources" section header is present.
    await expect(palette.locator('[data-testid="palette-resources-label"]')).toBeVisible({ timeout: 8_000 });

    // Dedupe regression — the rf-knowledge search path returns repo keywords
    // under a "library" named after the file stem ("login.resource" -> "login").
    // Those must NOT also appear as a separate library category below; they live
    // only in "Your resources". Assert no category is named after the stem.
    await expect(palette.locator('.category-name', { hasText: /^login$/i })).toHaveCount(0);

    // D5 / D6 — sort + filter controls live in the palette header.
    await expect(palette.locator('[data-testid="palette-sort-btn"]')).toBeVisible();
    await expect(palette.locator('[data-testid="palette-filter-btn"]')).toBeVisible();
    await palette.locator('[data-testid="palette-filter-btn"]').click();
    await expect(palette.locator('[data-testid="palette-filter-menu"]')).toBeVisible();
    // Close the menu again before interacting with the palette body.
    await palette.locator('[data-testid="palette-filter-btn"]').click();

    // Open the resource file category and select the keyword.
    const resHeader = palette.locator('.category-header', { hasText: 'login.resource' }).first();
    await expect(resHeader).toBeVisible({ timeout: 8_000 });
    if (!(await palette.getByText('Open Login Page', { exact: true }).first().isVisible().catch(() => false))) {
      await resHeader.click();
    }
    await palette.getByText('Open Login Page', { exact: true }).first().click();
    await palette.locator('.palette-add-btn').click();

    // D2 — an import-confirmation toast appears, naming the resource file.
    const toast = page.locator('.toast').filter({ hasText: /login\.resource/ });
    await expect(toast.first()).toBeVisible({ timeout: 6_000 });

    // D3 — the inserted node's detail panel opens with the required argument
    // slot already present (one `${url}` slot, not a bare "+ add argument").
    await expect(page.locator('.flow-arg-row').first()).toBeVisible({ timeout: 6_000 });

    // The auto-import landed in the generated .robot (Code tab).
    await page.locator('button', { hasText: /^Code$/ }).first().click();
    const code = page.locator('.cm-content');
    await expect(code).toBeVisible({ timeout: 8_000 });
    const text = (await code.innerText()).replace(/ /g, ' ');
    expect(text).toContain('Open Login Page');
    expect(text).toMatch(/Resource\s+\.\.\/resources\/login\.resource/);
  });
});
