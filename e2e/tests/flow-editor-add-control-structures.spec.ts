/**
 * Flow Editor — ADDING control structures through the UI (IF/ELSE + TRY/EXCEPT).
 *
 * The sibling `flow-editor-control-structures.spec.ts` only LOADS a pre-seeded
 * suite and checks the round-trip. This spec covers the thing a user actually
 * does by hand and reported as broken: open the Flow tab on a fresh file, build
 * an `IF / ELSE / END` and a `TRY / EXCEPT / END` block from the palette, and
 * confirm both land CLEANLY in the resulting test — in the Code tab, on disk
 * after Save, and stable across a reload.
 *
 * Regression guard for the two implementation fixes this exposed:
 *   1. the palette had no EXCEPT / FINALLY items, so a TRY block could never be
 *      completed (a bare `TRY ... END` is a Robot Framework syntax error);
 *   2. adding a TRY now scaffolds `TRY → EXCEPT → END` so it is valid RF out of
 *      the box.
 *
 * We drive the palette via single-click-to-select + the "+" add button rather
 * than double-click: the first double-click on a freshly-rendered palette is
 * swallowed because selecting an item reveals the add-bar and reflows the list
 * mid-gesture. The select + "+" path is a real, deterministic user workflow.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const SEED_ROBOT = `*** Test Cases ***
Control Demo
    Log    start
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  return (await res.json()).access_token as string;
}

async function createSeedRepo(page: Page, token: string): Promise<{ repoId: number; filePath: string }> {
  const stamp = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `flow-add-control-${stamp}`, repo_type: 'local', local_path: `/tmp/roboscope-flow-add-${stamp}` },
  });
  expect(res.status()).toBe(201);
  const repoId = (await res.json()).id as number;
  const filePath = 'tests/control.robot';
  await page.request.post(`${API}/explorer/${repoId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { path: filePath, content: SEED_ROBOT },
  });
  return { repoId, filePath };
}

async function openFileInFlow(page: Page, repoId: number) {
  await page.goto(`/explorer/${repoId}`);
  await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
  const testsFolder = page.locator('text=/^tests$/').first();
  await expect(testsFolder).toBeVisible({ timeout: 10_000 });
  const fileRow = page.locator('text=control.robot').first();
  if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
  await expect(fileRow).toBeVisible({ timeout: 8_000 });
  await fileRow.click();

  // Flow tab → canvas renders (Start node present).
  const flowTab = page.locator('button', { hasText: /^Flow$/ }).first();
  await expect(flowTab).toBeVisible({ timeout: 8_000 });
  await flowTab.click();
  await expect(page.locator('.vue-flow__node[data-id$="-start"]').first()).toBeVisible({ timeout: 8_000 });

  // Make sure the Control palette category is expanded.
  const ctrlHeader = page.locator('.keyword-palette .category-header', { hasText: 'Control' }).first();
  await expect(ctrlHeader).toBeVisible({ timeout: 8_000 });
  // Expand it if the IF item isn't already showing.
  const ifItem = page.locator('.palette-item-control', { has: page.getByText('IF / ELSE', { exact: true }) });
  if (!(await ifItem.first().isVisible().catch(() => false))) await ctrlHeader.click();
  await expect(ifItem.first()).toBeVisible({ timeout: 8_000 });
}

/** Clear the canvas selection so the next palette-add appends at the end of
 *  the active test case rather than splicing after the selected node. */
async function deselect(page: Page) {
  await page.locator('.vue-flow__pane').first().click({ position: { x: 8, y: 8 } });
}

/** Add a Control palette item via select + the "+" add button. */
async function addControl(page: Page, label: string) {
  const item = page
    .locator('.keyword-palette .palette-item-control', { has: page.getByText(label, { exact: true }) })
    .first();
  await item.click();
  const addBtn = page.locator('.keyword-palette .palette-add-btn');
  await expect(addBtn).toBeVisible({ timeout: 4_000 });
  await addBtn.click();
}

async function codeText(page: Page): Promise<string> {
  const codeTab = page.locator('button', { hasText: /^Code$/ }).first();
  await expect(codeTab).toBeVisible({ timeout: 8_000 });
  await codeTab.click();
  const code = page.locator('.cm-content');
  await expect(code).toBeVisible({ timeout: 8_000 });
  // CodeMirror renders NBSP for leading whitespace; normalise to plain spaces.
  return (await code.innerText()).replace(/ /g, ' ');
}

async function saveFile(page: Page) {
  const saveBtn = page.getByRole('button', { name: /Speichern|Save/ }).first();
  await expect(saveBtn).toBeVisible({ timeout: 8_000 });
  await saveBtn.click();
  // The unsaved badge disappears once the write round-trips.
  await expect(page.locator('.unsaved-badge')).toHaveCount(0, { timeout: 8_000 });
}

async function persistedContent(page: Page, repoId: number, filePath: string, token: string): Promise<string> {
  const res = await page.request.get(`${API}/explorer/${repoId}/file?path=${encodeURIComponent(filePath)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).content as string;
}

test.describe('Flow Editor — add control structures through the UI', () => {
  let token: string;
  let repoId: number;
  let filePath: string;

  test.beforeEach(async ({ page }) => {
    token = await getAuthToken(page);
    ({ repoId, filePath } = await createSeedRepo(page, token));
    await loginAndGoToDashboard(page);
  });

  test.afterEach(async ({ page }) => {
    if (repoId) {
      await page.request
        .delete(`${API}/repos/${repoId}`, { headers: { Authorization: `Bearer ${token}` } })
        .catch(() => {});
    }
  });

  test('builds an IF / ELSE / END block and it lands cleanly in the test', async ({ page }) => {
    await openFileInFlow(page, repoId);

    // Append an IF block (IF + matching END), then an ELSE branch inside it.
    await deselect(page);
    await addControl(page, 'IF / ELSE'); // → IF ... END, selection moves to IF
    await addControl(page, 'ELSE');      // IF selected → ELSE spliced before END

    const text = await codeText(page);
    expect(text).toContain('IF    ${condition}');
    expect(text).toContain('ELSE');
    expect((text.match(/^\s*END\s*$/gm) || []).length).toBe(1);
    // Order: IF before ELSE before its END.
    expect(text.indexOf('IF    ${condition}')).toBeLessThan(text.indexOf('ELSE'));
    expect(text.indexOf('ELSE')).toBeLessThan(text.lastIndexOf('END'));

    // Persisted to disk cleanly.
    await saveFile(page);
    const onDisk = await persistedContent(page, repoId, filePath, token);
    expect(onDisk).toMatch(/IF {4}\$\{condition\}/);
    expect(onDisk).toMatch(/^\s*ELSE\s*$/m);
    expect((onDisk.match(/^\s*END\s*$/gm) || []).length).toBe(1);

    // Reload the file fresh — the saved artifact reopens without corruption.
    await openFileInFlow(page, repoId);
    const reloaded = await codeText(page);
    expect(reloaded).toContain('IF    ${condition}');
    expect(reloaded).toContain('ELSE');
    expect((reloaded.match(/^\s*END\s*$/gm) || []).length).toBe(1);
  });

  test('builds a TRY / EXCEPT / END block and it lands cleanly in the test', async ({ page }) => {
    await openFileInFlow(page, repoId);

    // A TRY must carry at least one EXCEPT/ELSE/FINALLY to be valid RF — the
    // palette now scaffolds TRY → EXCEPT → END in one action.
    await deselect(page);
    await addControl(page, 'TRY / EXCEPT');

    const text = await codeText(page);
    expect(text).toContain('TRY');
    expect(text).toContain('EXCEPT');
    expect((text.match(/^\s*END\s*$/gm) || []).length).toBe(1);
    // Order: TRY before EXCEPT before END.
    expect(text.indexOf('TRY')).toBeLessThan(text.indexOf('EXCEPT'));
    expect(text.indexOf('EXCEPT')).toBeLessThan(text.lastIndexOf('END'));

    // Persisted to disk cleanly.
    await saveFile(page);
    const onDisk = await persistedContent(page, repoId, filePath, token);
    expect(onDisk).toMatch(/^\s*TRY\s*$/m);
    expect(onDisk).toMatch(/^\s*EXCEPT\s*$/m);
    expect((onDisk.match(/^\s*END\s*$/gm) || []).length).toBe(1);

    // Reload — saved artifact reopens intact.
    await openFileInFlow(page, repoId);
    const reloaded = await codeText(page);
    expect(reloaded).toContain('TRY');
    expect(reloaded).toContain('EXCEPT');
    expect((reloaded.match(/^\s*END\s*$/gm) || []).length).toBe(1);
  });
});
