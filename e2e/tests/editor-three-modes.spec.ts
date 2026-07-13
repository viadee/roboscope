/**
 * Editor — all three modes (Flow / Visueller Editor / Code) + mode switching.
 *
 * Covers the authoring gap from the use-case audit (2026-07-02):
 *  - switching Flow → Visual → Code → Flow must not lose data,
 *  - creating a test case by TYPING in the Code tab must surface in the
 *    other modes and persist via the save button,
 *  - creating a test case in the Visual tab must round-trip to Code.
 *
 * Fixtures seed ≥2 test cases (mandatory for flow-editor fixtures — the
 * deep form-watcher reset to item #0 is invisible with a single case).
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const MODES_ROBOT = `*** Settings ***
Documentation    Editor mode-switch fixture

*** Test Cases ***
First Test
    Log    hello first

Second Test
    Log    hello second
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

async function seedFile(page: Page, token: string, repoId: number, path: string, content: string) {
  const res = await page.request.post(`${API}/explorer/${repoId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { path, content },
  });
  expect(res.status()).toBeLessThan(300);
}

async function openFileInEditor(page: Page, repoId: number, fileName: string) {
  await page.goto(`/explorer/${repoId}`);
  await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
  const testsFolder = page.locator('text=/^tests$/').first();
  await expect(testsFolder).toBeVisible({ timeout: 10_000 });
  const fileRow = page.locator(`text=${fileName}`).first();
  if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
  await expect(fileRow).toBeVisible({ timeout: 8_000 });
  await fileRow.click();
  // Editor opens on the Flow tab by default
  await expect(page.locator('button.tab-btn', { hasText: /^Flow$/ })).toBeVisible({ timeout: 8_000 });
}

async function switchToTab(page: Page, label: RegExp) {
  await page.locator('button.tab-btn', { hasText: label }).first().click();
}

/** Read the CodeMirror buffer, normalising the NBSPs it uses for indentation. */
async function readCode(page: Page): Promise<string> {
  const code = page.locator('.cm-content');
  await expect(code).toBeVisible({ timeout: 8_000 });
  return (await code.innerText()).replace(/ /g, ' ');
}

test.describe.serial('Editor — three modes', () => {
  let token: string;
  let repoId: number;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    token = await getAuthToken(page);
    const stamp = Date.now();
    const res = await page.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: `editor-modes-e2e-${stamp}`, repo_type: 'local', local_path: `/tmp/roboscope-editor-modes-${stamp}` },
    });
    expect(res.status()).toBe(201);
    repoId = (await res.json()).id as number;
    await seedFile(page, token, repoId, 'tests/modes.robot', MODES_ROBOT);
    await seedFile(page, token, repoId, 'tests/edit.robot', MODES_ROBOT);
    await seedFile(page, token, repoId, 'tests/visual.robot', MODES_ROBOT);
    await page.close();
  });

  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    const t = await getAuthToken(page);
    await page.request.delete(`${API}/repos/${repoId}`, { headers: { Authorization: `Bearer ${t}` } });
    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('Flow → Visual → Code → Flow round-trip loses no data', async ({ page }) => {
    await openFileInEditor(page, repoId, 'modes.robot');

    // Flow (default): canvas rendered, badge counts both tests
    await expect(page.locator('.vue-flow__node').first()).toBeVisible({ timeout: 8_000 });
    await expect(page.locator('.badge-info', { hasText: '2' }).first()).toBeVisible();

    // Code: both test cases present
    await switchToTab(page, /^Code$/);
    const before = await readCode(page);
    expect(before).toContain('First Test');
    expect(before).toContain('Second Test');
    expect(before).toContain('Documentation    Editor mode-switch fixture');

    // Visual: both item cards listed
    await switchToTab(page, /Visueller Editor/);
    await expect(page.locator('.visual-editor')).toBeVisible();
    await expect(page.locator('.item-title', { hasText: 'First Test' })).toBeVisible();
    await expect(page.locator('.item-title', { hasText: 'Second Test' })).toBeVisible();

    // Back to Flow, then Code again — buffer must be equivalent
    await switchToTab(page, /^Flow$/);
    await expect(page.locator('.vue-flow__node').first()).toBeVisible({ timeout: 8_000 });
    await switchToTab(page, /^Code$/);
    const after = await readCode(page);
    expect(after.trim()).toBe(before.trim());
  });

  test('typing a new test case in Code mode surfaces in Flow and persists on save', async ({ page }) => {
    await openFileInEditor(page, repoId, 'edit.robot');
    await switchToTab(page, /^Code$/);
    const code = page.locator('.cm-content');
    await expect(code).toBeVisible({ timeout: 8_000 });

    // Append a third test case at the end of the buffer
    await code.click();
    await page.keyboard.press('ControlOrMeta+End');
    await page.keyboard.insertText('\nThird Test\n    Log    hello third\n');

    // Flow reflects the parse: badge now counts 3 tests
    await switchToTab(page, /^Flow$/);
    await expect(page.locator('.badge-info', { hasText: '3' }).first()).toBeVisible({ timeout: 8_000 });

    // Save via the editor toolbar and verify on disk via the API
    const saveBtn = page.getByRole('button', { name: /Speichern|Save/ }).first();
    await expect(saveBtn).toBeVisible({ timeout: 8_000 });
    await saveBtn.click();
    await expect(page.locator('.unsaved-badge')).toHaveCount(0, { timeout: 8_000 });
    await expect(async () => {
      const res = await page.request.get(`${API}/explorer/${repoId}/file`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { path: 'tests/edit.robot' },
      });
      expect(res.status()).toBe(200);
      const body = await res.json();
      expect(body.content).toContain('Third Test');
      expect(body.content).toContain('hello third');
    }).toPass({ timeout: 10_000 });
  });

  test('adding a test case in Visual mode round-trips to Code', async ({ page }) => {
    await openFileInEditor(page, repoId, 'visual.robot');
    await switchToTab(page, /Visueller Editor/);
    await expect(page.locator('.visual-editor')).toBeVisible();

    // Add an (initially unnamed) test case, then name it
    await page.getByRole('button', { name: /Testfall hinzufügen/ }).click();
    const newCard = page.locator('.item-card', { hasText: 'Unbenannter Testfall' }).first();
    await expect(newCard).toBeVisible();
    // The content echo re-parses the form shortly after the add and
    // re-collapses every card — wait it out, then expand with retry.
    await page.waitForTimeout(1000);
    const nameInput = newCard.getByPlaceholder('Mein Testfall');
    await expect(async () => {
      if (!(await nameInput.isVisible().catch(() => false))) {
        await newCard.locator('.item-header').click();
      }
      await expect(nameInput).toBeVisible({ timeout: 1_500 });
    }).toPass({ timeout: 10_000 });
    await nameInput.fill('Visual Added Test');

    // Round-trip to Code
    await switchToTab(page, /^Code$/);
    const text = await readCode(page);
    expect(text).toContain('Visual Added Test');
    // The seeded cases must survive the visual edit untouched
    expect(text).toContain('First Test');
    expect(text).toContain('Second Test');
  });
});
