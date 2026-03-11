import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  const body = await res.json();
  return body.access_token;
}

async function createTestRepo(
  page: Page,
  token: string,
  suffix: string,
): Promise<{ repoId: number; repoName: string }> {
  const repoName = `remember-pos-${suffix}-${Date.now()}`;
  const localPath = `/tmp/roboscope-remember-${suffix}-${Date.now()}`;

  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: repoName, repo_type: 'local', local_path: localPath },
  });
  expect(res.status()).toBe(201);
  const body = await res.json();

  // Create a Python file (uses CodeMirror editor — easier to test cursor)
  await page.request.post(`${API}/explorer/${body.id}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      path: 'libs/utils.py',
      content: 'def hello():\n    return "world"\n\ndef foo():\n    return "bar"\n',
    },
  });

  // Create a second file
  await page.request.post(`${API}/explorer/${body.id}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      path: 'libs/other.py',
      content: 'import os\nimport sys\nprint("other")\n',
    },
  });

  return { repoId: body.id, repoName };
}

async function cleanupRepo(page: Page, token: string, repoId: number) {
  await page.request.delete(`${API}/repos/${repoId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

async function goToExplorer(page: Page, repoId?: number) {
  const url = repoId ? `/explorer/${repoId}` : '/explorer';
  await page.goto(url);
  await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(1000);
}

async function openFileInTree(page: Page, dirName: string, fileName: string) {
  // Wait for tree to be rendered
  await page.locator('.tree-content').waitFor({ state: 'visible', timeout: 10_000 });

  // Expand directory if file is not already visible
  const fileNode = page.locator('.node-name', { hasText: fileName });
  if (!(await fileNode.isVisible())) {
    const dir = page.locator('.tree-node .node-name', { hasText: new RegExp(`^${dirName}$`) });
    await dir.waitFor({ state: 'visible', timeout: 5000 });
    await dir.click();
    await page.waitForTimeout(300);
  }

  // Click file
  await fileNode.click();
  await page.waitForTimeout(500);
}

test.describe('Explorer — Remember Position', () => {
  let token: string;
  let repoId1: number;
  let repoId2: number;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    token = await getAuthToken(page);
    const repo1 = await createTestRepo(page, token, 'a');
    const repo2 = await createTestRepo(page, token, 'b');
    repoId1 = repo1.repoId;
    repoId2 = repo2.repoId;
    await page.close();
  });

  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    const t = await getAuthToken(page);
    await cleanupRepo(page, t, repoId1);
    await cleanupRepo(page, t, repoId2);
    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('navigating away and back restores the selected file', async ({ page }) => {
    await goToExplorer(page, repoId1);

    // Open utils.py
    await openFileInTree(page, 'libs', 'utils.py');
    await expect(page.locator('.breadcrumb-current')).toHaveText('utils.py');
    await expect(page.locator('.cm-editor')).toBeVisible();

    // Navigate away to dashboard
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Navigate back to explorer (without repoId in URL)
    await goToExplorer(page);

    // File should be restored
    await expect(page.locator('.breadcrumb-current')).toHaveText('utils.py', { timeout: 5000 });
    await expect(page.locator('.cm-editor')).toBeVisible();
  });

  test('last repo is remembered when navigating to /explorer without repoId', async ({ page }) => {
    // Visit repo1
    await goToExplorer(page, repoId1);

    // Verify the repo select shows repo1
    const select = page.locator('.form-select');
    await expect(select).toHaveValue(String(repoId1));

    // Navigate away
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Navigate to /explorer without specifying repo
    await goToExplorer(page);

    // Should restore repo1
    await expect(select).toHaveValue(String(repoId1));
  });

  test('switching repos remembers each repo\'s last file independently', async ({ page }) => {
    // Open file in repo1
    await goToExplorer(page, repoId1);
    await openFileInTree(page, 'libs', 'utils.py');
    await expect(page.locator('.breadcrumb-current')).toHaveText('utils.py');

    // Switch to repo2 via dropdown
    const select = page.locator('.form-select');
    await select.selectOption(String(repoId2));
    await page.waitForTimeout(1000);

    // Open other.py in repo2
    await openFileInTree(page, 'libs', 'other.py');
    await expect(page.locator('.breadcrumb-current')).toHaveText('other.py');

    // Switch back to repo1
    await select.selectOption(String(repoId1));
    await page.waitForTimeout(1000);

    // Should restore utils.py (repo1's last file)
    await expect(page.locator('.breadcrumb-current')).toHaveText('utils.py', { timeout: 5000 });

    // Switch back to repo2
    await select.selectOption(String(repoId2));
    await page.waitForTimeout(1000);

    // Should restore other.py (repo2's last file)
    await expect(page.locator('.breadcrumb-current')).toHaveText('other.py', { timeout: 5000 });
  });

  test('cursor position is saved to localStorage and restored', async ({ page }) => {
    await goToExplorer(page, repoId1);

    // Open utils.py (CodeMirror editor)
    await openFileInTree(page, 'libs', 'utils.py');
    await expect(page.locator('.cm-editor')).toBeVisible();

    // Place cursor by clicking on the editor and using keyboard
    const editor = page.locator('.cm-content');
    await editor.click();
    // Move cursor down a couple lines so it's not at position 0
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('End');
    await page.waitForTimeout(200);

    // Navigate away via sidebar (SPA navigation — triggers Vue onUnmounted)
    await page.locator('.nav-item', { hasText: 'Dashboard' }).click();
    await page.waitForURL('**/dashboard');
    await page.waitForTimeout(500);

    // Verify cursor state was saved to localStorage
    const cursorData = await page.evaluate((repoId) => {
      const raw = localStorage.getItem(`explorer-cursor-${repoId}`);
      return raw ? JSON.parse(raw) : null;
    }, repoId1);
    expect(cursorData).not.toBeNull();
    expect(cursorData.path).toBe('libs/utils.py');
    expect(cursorData.cursor).toBeGreaterThan(0);

    // Navigate back via sidebar
    await page.locator('.nav-item', { hasText: 'Explorer' }).click();
    await page.waitForURL('**/explorer/**');
    await expect(page.locator('.cm-editor')).toBeVisible({ timeout: 5000 });
    await page.waitForTimeout(500);

    // Verify the active line is highlighted (cursor was restored, not at line 1)
    const activeLine = page.locator('.cm-activeLine');
    await expect(activeLine).toBeVisible();
    // The active line should contain content from line 3+ (not line 1 "def hello():")
    const activeText = await activeLine.textContent();
    expect(activeText).not.toContain('def hello');
  });

  test('deleted file is handled gracefully — no file restored', async ({ page }) => {
    await goToExplorer(page, repoId1);

    // Create a temp file, open it, then delete it externally
    await page.request.post(`${API}/explorer/${repoId1}/file`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { path: 'libs/temp.py', content: '# temp\n' },
    });

    // Refresh tree and open the temp file
    await goToExplorer(page, repoId1);
    await openFileInTree(page, 'libs', 'temp.py');
    await expect(page.locator('.breadcrumb-current')).toHaveText('temp.py');

    // Delete the file via API
    await page.request.delete(`${API}/explorer/${repoId1}/file?path=libs/temp.py`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    // Navigate away and back
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await goToExplorer(page);

    // File no longer exists in tree — should show empty state, not crash
    await expect(page.locator('.breadcrumb-current')).not.toBeVisible({ timeout: 3000 });
    await expect(page.locator('.empty-state')).toBeVisible();
  });

  test('browser refresh restores repo and file', async ({ page }) => {
    await goToExplorer(page, repoId1);

    // Open utils.py
    await openFileInTree(page, 'libs', 'utils.py');
    await expect(page.locator('.breadcrumb-current')).toHaveText('utils.py');

    // Reload the page (keeps localStorage)
    await page.reload();
    await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(1500);

    // File should be restored
    await expect(page.locator('.breadcrumb-current')).toHaveText('utils.py', { timeout: 5000 });
  });
});
