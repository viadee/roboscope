import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@mateox.local';
const PASSWORD = 'admin123';

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  const body = await res.json();
  return body.access_token;
}

/** Create a local repo with a test file for explorer testing. */
async function createTestRepo(page: Page, token: string): Promise<{ repoId: number; repoName: string; localPath: string }> {
  const repoName = `explorer-e2e-${Date.now()}`;
  const localPath = `/tmp/mateox-explorer-${Date.now()}`;

  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: repoName,
      repo_type: 'local',
      local_path: localPath,
    },
  });
  expect(res.status()).toBe(201);
  const body = await res.json();

  // Create a test .robot file
  await page.request.post(`${API}/explorer/${body.id}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      path: 'tests/sample.robot',
      content: '*** Settings ***\nLibrary    Collections\n\n*** Test Cases ***\nSample Test\n    Log    Hello from sample\n',
    },
  });

  // Create a Python file
  await page.request.post(`${API}/explorer/${body.id}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      path: 'libs/helper.py',
      content: 'def greet(name: str) -> str:\n    return f"Hello {name}"\n',
    },
  });

  return { repoId: body.id, repoName, localPath };
}

async function cleanupRepo(page: Page, token: string, repoId: number) {
  await page.request.delete(`${API}/repos/${repoId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

async function goToExplorer(page: Page, repoId: number) {
  await page.goto(`/explorer/${repoId}`);
  await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
  // Wait for tree to load
  await page.waitForTimeout(1000);
}

test.describe('Explorer — E2E', () => {
  let token: string;
  let repoId: number;
  let repoName: string;
  let localPath: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    token = await getAuthToken(page);
    const repo = await createTestRepo(page, token);
    repoId = repo.repoId;
    repoName = repo.repoName;
    localPath = repo.localPath;
    await page.close();
  });

  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    const t = await getAuthToken(page);
    await cleanupRepo(page, t, repoId);
    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  // ─── API-Level Tests ─────────────────────────────────────────────

  test('GET /explorer/{id}/tree returns file tree', async ({ page }) => {
    const res = await page.request.get(`${API}/explorer/${repoId}/tree`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
    const tree = await res.json();
    expect(tree.type).toBe('directory');
    expect(tree.children.length).toBeGreaterThanOrEqual(2); // tests/ and libs/
  });

  test('GET /explorer/{id}/file returns file content', async ({ page }) => {
    const res = await page.request.get(`${API}/explorer/${repoId}/file?path=tests/sample.robot`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
    const file = await res.json();
    expect(file.name).toBe('sample.robot');
    expect(file.content).toContain('Sample Test');
    expect(file.extension).toBe('.robot');
  });

  test('POST /explorer/{id}/file creates a new file', async ({ page }) => {
    const res = await page.request.post(`${API}/explorer/${repoId}/file`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { path: 'tests/new_test.robot', content: '*** Test Cases ***\nNew\n    Log    new\n' },
    });
    expect(res.status()).toBe(201);
    const file = await res.json();
    expect(file.name).toBe('new_test.robot');

    // Clean up
    await page.request.delete(`${API}/explorer/${repoId}/file?path=tests/new_test.robot`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  });

  test('PUT /explorer/{id}/file saves file content', async ({ page }) => {
    // Create a temp file
    await page.request.post(`${API}/explorer/${repoId}/file`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { path: 'temp_save.txt', content: 'original' },
    });

    const res = await page.request.put(`${API}/explorer/${repoId}/file`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { path: 'temp_save.txt', content: 'updated content' },
    });
    expect(res.status()).toBe(200);
    const file = await res.json();
    expect(file.content).toBe('updated content');

    // Verify
    const read = await page.request.get(`${API}/explorer/${repoId}/file?path=temp_save.txt`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const readFile = await read.json();
    expect(readFile.content).toBe('updated content');

    // Clean up
    await page.request.delete(`${API}/explorer/${repoId}/file?path=temp_save.txt`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  });

  test('DELETE /explorer/{id}/file deletes a file', async ({ page }) => {
    // Create a temp file
    await page.request.post(`${API}/explorer/${repoId}/file`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { path: 'to_delete.txt', content: 'delete me' },
    });

    const res = await page.request.delete(`${API}/explorer/${repoId}/file?path=to_delete.txt`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(204);

    // Verify it's gone
    const check = await page.request.get(`${API}/explorer/${repoId}/file?path=to_delete.txt`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(check.status()).toBe(404);
  });

  test('POST /explorer/{id}/file/rename renames a file', async ({ page }) => {
    // Create temp file
    await page.request.post(`${API}/explorer/${repoId}/file`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { path: 'old_name.txt', content: 'content' },
    });

    const res = await page.request.post(`${API}/explorer/${repoId}/file/rename`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { old_path: 'old_name.txt', new_path: 'new_name.txt' },
    });
    expect(res.status()).toBe(200);
    const file = await res.json();
    expect(file.name).toBe('new_name.txt');

    // Clean up
    await page.request.delete(`${API}/explorer/${repoId}/file?path=new_name.txt`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  });

  // ─── UI Tests ─────────────────────────────────────────────────────

  test('UI: folder navigation - can expand/collapse directories', async ({ page }) => {
    await goToExplorer(page, repoId);

    // The tree should show directories (use .node-name to avoid matching header)
    const testsDir = page.locator('.tree-node .node-name', { hasText: /^tests$/ });
    const libsDir = page.locator('.tree-node .node-name', { hasText: /^libs$/ });
    await expect(testsDir).toBeVisible();
    await expect(libsDir).toBeVisible();

    // Click "tests" directory to expand
    await testsDir.click();
    await page.waitForTimeout(300);

    // Should now see sample.robot inside tests
    await expect(page.locator('.node-name', { hasText: 'sample.robot' })).toBeVisible();

    // Click "tests" again to collapse
    await testsDir.click();
    await page.waitForTimeout(300);

    // sample.robot should be hidden
    await expect(page.locator('.node-name', { hasText: 'sample.robot' })).not.toBeVisible();
  });

  test('UI: clicking a file opens it in the editor', async ({ page }) => {
    await goToExplorer(page, repoId);

    // Expand tests directory
    const testsDir = page.locator('.tree-node .node-name', { hasText: /^tests$/ });
    await testsDir.click();
    await page.waitForTimeout(300);

    // Click sample.robot
    await page.locator('.node-name', { hasText: 'sample.robot' }).click();
    await page.waitForTimeout(500);

    // Editor should show with file content
    await expect(page.locator('.breadcrumb-current')).toHaveText('sample.robot');
    // CodeMirror editor should be present
    await expect(page.locator('.cm-editor')).toBeVisible();
    // Content should include our test case
    await expect(page.locator('.cm-content')).toContainText('Sample Test');
  });

  test('UI: create new file via dialog', async ({ page }) => {
    await goToExplorer(page, repoId);

    // Click the + button in tree header
    await page.locator('.tree-header .icon-btn').click();
    await page.waitForTimeout(300);

    // Modal should appear
    await expect(page.getByText('Neue Datei anlegen')).toBeVisible();

    // Enter file path
    await page.locator('input[placeholder*="tests/neue_tests"]').fill('tests/created_via_ui.robot');
    await page.getByRole('button', { name: 'Anlegen' }).click();
    await page.waitForTimeout(500);

    // Verify via API that file was created
    const res = await page.request.get(`${API}/explorer/${repoId}/file?path=tests/created_via_ui.robot`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);

    // Clean up
    await page.request.delete(`${API}/explorer/${repoId}/file?path=tests/created_via_ui.robot`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  });

  test('UI: Python file gets syntax highlighting', async ({ page }) => {
    await goToExplorer(page, repoId);

    // Expand libs directory
    await page.locator('.tree-node .node-name', { hasText: /^libs$/ }).click();
    await page.waitForTimeout(300);

    // Click helper.py
    await page.locator('.node-name', { hasText: 'helper.py' }).click();
    await page.waitForTimeout(500);

    // Editor should be present
    await expect(page.locator('.cm-editor')).toBeVisible();
    // Content should show Python code
    await expect(page.locator('.cm-content')).toContainText('def greet');
  });

  test('UI: search finds test cases', async ({ page }) => {
    await goToExplorer(page, repoId);

    // Use the search
    await page.locator('input[placeholder*="suchen"]').fill('Sample Test');
    await page.getByRole('button', { name: 'Suchen' }).click();
    await page.waitForTimeout(500);

    // Search results should appear
    await expect(page.getByText('Suchergebnisse')).toBeVisible();
    await expect(page.locator('.search-item').first()).toBeVisible();
  });
});
