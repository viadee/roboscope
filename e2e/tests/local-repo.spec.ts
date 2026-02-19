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

async function goToRepos(page: Page) {
  await page.goto('/repos');
  await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });
}

test.describe('Local Repository — E2E', () => {
  let token: string;

  test.beforeEach(async ({ page }) => {
    token = await getAuthToken(page);
    await loginAndGoToDashboard(page);
  });

  // ─── API-Level Tests ─────────────────────────────────────────────

  test('POST /repos should create a local repo without git_url', async ({ page }) => {
    const repoName = `local-api-${Date.now()}`;
    const localPath = `/tmp/mateox-e2e-${Date.now()}`;

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
    expect(body.repo_type).toBe('local');
    expect(body.git_url).toBeNull();
    expect(body.local_path).toBe(localPath);
    expect(body.auto_sync).toBe(false);

    // Cleanup
    await page.request.delete(`${API}/repos/${body.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  });

  test('POST /repos should reject local repo without local_path', async ({ page }) => {
    const res = await page.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        name: `local-nopath-${Date.now()}`,
        repo_type: 'local',
      },
    });
    expect(res.status()).toBe(422);
  });

  test('POST /repos should reject git repo without git_url', async ({ page }) => {
    const res = await page.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        name: `git-nourl-${Date.now()}`,
        repo_type: 'git',
      },
    });
    expect(res.status()).toBe(422);
  });

  test('sync endpoint should return skipped for local repos', async ({ page }) => {
    const repoName = `local-sync-${Date.now()}`;
    const createRes = await page.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: repoName, repo_type: 'local', local_path: `/tmp/mateox-sync-${Date.now()}` },
    });
    const repo = await createRes.json();

    const syncRes = await page.request.post(`${API}/repos/${repo.id}/sync`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(syncRes.ok()).toBeTruthy();
    const syncBody = await syncRes.json();
    expect(syncBody.status).toBe('skipped');

    // Cleanup
    await page.request.delete(`${API}/repos/${repo.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  });

  test('GET /repos should return repo_type field', async ({ page }) => {
    const repoName = `local-list-${Date.now()}`;
    const createRes = await page.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: repoName, repo_type: 'local', local_path: `/tmp/mateox-list-${Date.now()}` },
    });
    const repo = await createRes.json();

    const listRes = await page.request.get(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const repos = await listRes.json();
    const found = repos.find((r: any) => r.id === repo.id);
    expect(found).toBeTruthy();
    expect(found.repo_type).toBe('local');

    // Cleanup
    await page.request.delete(`${API}/repos/${repo.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  });

  // ─── UI-Level Tests ──────────────────────────────────────────────

  test('add repo dialog should have type toggle', async ({ page }) => {
    await goToRepos(page);
    await page.getByRole('button', { name: /Projekt hinzufügen/ }).click();

    // Type toggle should be visible
    await expect(page.getByText('Git Repository')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Lokaler Ordner')).toBeVisible();
  });

  test('should create a local repo via UI', async ({ page }) => {
    const repoName = `local-ui-${Date.now()}`;
    const localPath = `/tmp/mateox-ui-${Date.now()}`;

    await goToRepos(page);
    await page.getByRole('button', { name: /Projekt hinzufügen/ }).click();

    // Switch to local type
    await page.getByText('Lokaler Ordner').click();

    // Git URL field should disappear, local path should appear
    await expect(page.getByPlaceholder('https://github.com/user/repo.git')).not.toBeVisible();
    await expect(page.getByPlaceholder('/pfad/zum/ordner')).toBeVisible();

    // Fill form
    await page.getByPlaceholder('mein-projekt').fill(repoName);
    await page.getByPlaceholder('/pfad/zum/ordner').fill(localPath);

    // Submit
    await page.getByRole('button', { name: 'Hinzufügen', exact: true }).click();

    // Modal should close and repo should appear with "Lokal" badge
    await expect(page.getByPlaceholder('mein-projekt')).not.toBeVisible({ timeout: 5_000 });
    const repoCard = page.locator('.card', { hasText: repoName });
    await expect(repoCard).toBeVisible({ timeout: 5_000 });
    await expect(repoCard.getByText('Lokal')).toBeVisible();
    await expect(repoCard.getByText(localPath).first()).toBeVisible();

    // Sync button should NOT be visible for local repos
    await expect(repoCard.getByRole('button', { name: 'Sync' })).not.toBeVisible();
  });

  test('local repo card should show path instead of git URL', async ({ page }) => {
    const repoName = `local-card-${Date.now()}`;
    const localPath = `/tmp/mateox-card-${Date.now()}`;

    await page.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: repoName, repo_type: 'local', local_path: localPath },
    });

    await goToRepos(page);

    const repoCard = page.locator('.card', { hasText: repoName });
    await expect(repoCard).toBeVisible({ timeout: 5_000 });

    // Should show "Lokal" badge
    await expect(repoCard.getByText('Lokal')).toBeVisible();
    // Should show the local path
    await expect(repoCard.getByText(localPath).first()).toBeVisible();
    // Should show "Pfad:" label
    await expect(repoCard.getByText('Pfad:')).toBeVisible();
    // Should NOT show git-specific fields
    await expect(repoCard.getByText('Branch:')).not.toBeVisible();
    await expect(repoCard.getByText('Letzter Sync:')).not.toBeVisible();
  });
});
