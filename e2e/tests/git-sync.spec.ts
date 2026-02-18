import { test, expect, type Page, type Route } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@mateox.local';
const PASSWORD = 'admin123';

/**
 * Helper: get a fresh auth token via API.
 */
async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  const body = await res.json();
  return body.access_token;
}

/**
 * Helper: create a repo via API with auth and return its data.
 */
async function createRepoViaApi(page: Page, token: string, name: string, gitUrl: string) {
  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name,
      git_url: gitUrl,
      default_branch: 'main',
      auto_sync: false,
      sync_interval_minutes: 15,
    },
  });
  return { status: res.status(), body: await res.json().catch(() => null) };
}

/**
 * Helper: navigate to repos page and wait for heading.
 */
async function goToRepos(page: Page) {
  await page.goto('/repos');
  await expect(page.locator('h1', { hasText: 'Repositories' })).toBeVisible({ timeout: 10_000 });
}

test.describe('Git Sync — E2E', () => {
  let token: string;

  test.beforeEach(async ({ page }) => {
    token = await getAuthToken(page);
    await loginAndGoToDashboard(page);
  });

  // ─── API-Level Tests ─────────────────────────────────────────────

  test('POST /repos/{id}/sync should return sync response', async ({ page }) => {
    const repoName = `sync-api-${Date.now()}`;
    const created = await createRepoViaApi(page, token, repoName, 'https://github.com/robotframework/example.git');
    expect(created.status).toBe(201);
    const repoId = created.body.id;

    // Call sync endpoint directly
    const syncRes = await page.request.post(`${API}/repos/${repoId}/sync`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const syncBody = await syncRes.json().catch(() => null);

    if (syncRes.ok()) {
      expect(syncBody).toHaveProperty('status');
      expect(syncBody).toHaveProperty('message');
      expect(syncBody.status).toBe('syncing');
      expect(syncBody.task_id).toBeTruthy();
    } else {
      // Log the failure for diagnosis
      console.error('Sync API failed:', syncRes.status(), syncBody);
      expect.soft(syncRes.ok(), `Sync returned ${syncRes.status()}: ${JSON.stringify(syncBody)}`).toBeTruthy();
    }
  });

  test('POST /repos/{id}/sync should return 404 for non-existent repo', async ({ page }) => {
    const res = await page.request.post(`${API}/repos/99999/sync`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(404);
  });

  test('sync endpoint should reject invalid token', async ({ page }) => {
    const res = await page.request.post(`${API}/repos/1/sync`, {
      headers: { Authorization: 'Bearer invalid-token' },
    });
    // Backend returns 401 for invalid tokens, 403 for insufficient role
    expect([401, 403]).toContain(res.status());
  });

  // ─── UI-Level Tests ──────────────────────────────────────────────

  test('sync button should be visible for admin user', async ({ page }) => {
    const repoName = `sync-ui-vis-${Date.now()}`;
    await createRepoViaApi(page, token, repoName, 'https://github.com/test/repo.git');

    await goToRepos(page);

    const repoCard = page.locator('.card', { hasText: repoName });
    await expect(repoCard).toBeVisible({ timeout: 5_000 });

    const syncButton = repoCard.getByRole('button', { name: 'Sync' });
    await expect(syncButton).toBeVisible();
  });

  test('clicking sync should call the sync API endpoint', async ({ page }) => {
    const repoName = `sync-ui-click-${Date.now()}`;
    const created = await createRepoViaApi(page, token, repoName, 'https://github.com/test/repo.git');
    const repoId = created.body.id;

    // Intercept the sync API call
    let syncCalled = false;
    let syncResponseStatus = 0;
    let syncResponseBody: Record<string, unknown> | null = null;

    await page.route(`**/api/v1/repos/${repoId}/sync`, async (route: Route) => {
      syncCalled = true;
      const response = await route.fetch();
      syncResponseStatus = response.status();
      syncResponseBody = await response.json().catch(() => null);
      console.log(`Sync response: ${syncResponseStatus}`, syncResponseBody);
      await route.fulfill({ response });
    });

    await goToRepos(page);

    const repoCard = page.locator('.card', { hasText: repoName });
    await expect(repoCard).toBeVisible({ timeout: 5_000 });
    await repoCard.getByRole('button', { name: 'Sync' }).click();

    // Wait for the API call
    await page.waitForTimeout(2_000);

    expect(syncCalled).toBe(true);
  });

  test('sync should show toast notification on success', async ({ page }) => {
    const repoName = `sync-toast-${Date.now()}`;
    const created = await createRepoViaApi(page, token, repoName, 'https://github.com/test/repo.git');
    const repoId = created.body.id;

    // Mock the sync API to succeed
    await page.route(`**/api/v1/repos/${repoId}/sync`, async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'syncing',
          message: 'Sync started',
          task_id: 'mock-task-123',
        }),
      });
    });

    await goToRepos(page);

    const repoCard = page.locator('.card', { hasText: repoName });
    await expect(repoCard).toBeVisible({ timeout: 5_000 });
    await repoCard.getByRole('button', { name: 'Sync' }).click();

    // Should show an info toast with "Sync"
    await expect(page.locator('.toast', { hasText: /Sync/ })).toBeVisible({ timeout: 5_000 });
  });

  test('sync should show error toast on failure', async ({ page }) => {
    const repoName = `sync-err-${Date.now()}`;
    const created = await createRepoViaApi(page, token, repoName, 'https://github.com/test/repo.git');
    const repoId = created.body.id;

    // Mock the sync API to fail
    await page.route(`**/api/v1/repos/${repoId}/sync`, async (route: Route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Celery broker unreachable' }),
      });
    });

    await goToRepos(page);

    const repoCard = page.locator('.card', { hasText: repoName });
    await expect(repoCard).toBeVisible({ timeout: 5_000 });
    await repoCard.getByRole('button', { name: 'Sync' }).click();

    // Should show an error toast
    await expect(page.locator('.toast', { hasText: /fehlgeschlagen/i })).toBeVisible({ timeout: 5_000 });
  });

  // ─── Full Flow: Add Repo via UI + Sync ────────────────────────────

  test('full flow: add repo via UI and trigger sync', async ({ page }) => {
    const repoName = `sync-flow-${Date.now()}`;
    const gitUrl = 'https://github.com/robotframework/example.git';

    await goToRepos(page);

    // Open modal and fill the form
    await page.getByRole('button', { name: /Repository hinzufügen/ }).click();
    await expect(page.getByPlaceholder('mein-projekt')).toBeVisible({ timeout: 3_000 });

    await page.getByPlaceholder('mein-projekt').fill(repoName);
    await page.getByPlaceholder('https://github.com/user/repo.git').fill(gitUrl);

    // Submit
    await page.getByRole('button', { name: 'Hinzufügen', exact: true }).click();

    // Modal should close and repo should appear
    await expect(page.getByPlaceholder('mein-projekt')).not.toBeVisible({ timeout: 5_000 });
    const repoCard = page.locator('.card', { hasText: repoName });
    await expect(repoCard).toBeVisible({ timeout: 5_000 });

    // Verify Git URL is shown
    await expect(repoCard.getByText(gitUrl)).toBeVisible();

    // Verify Sync button exists and click it
    const syncButton = repoCard.getByRole('button', { name: 'Sync' });
    await expect(syncButton).toBeVisible();

    // Intercept sync call to capture result
    let syncStatus = 0;
    let syncBody: Record<string, unknown> = {};
    await page.route('**/api/v1/repos/*/sync', async (route: Route) => {
      const response = await route.fetch();
      syncStatus = response.status();
      syncBody = await response.json().catch(() => ({}));
      console.log(`Sync result: HTTP ${syncStatus}`, syncBody);
      await route.fulfill({ response });
    });

    await syncButton.click();

    // Wait for the request + toast
    await page.waitForTimeout(2_000);

    // Verify a toast appeared (either success or error)
    const toasts = page.locator('.toast');
    await expect(toasts.first()).toBeVisible({ timeout: 3_000 });
  });

  // ─── Repo card: last_synced_at ────────────────────────────────────

  test('repo card should display last sync time field', async ({ page }) => {
    const repoName = `sync-time-${Date.now()}`;
    await createRepoViaApi(page, token, repoName, 'https://github.com/test/repo.git');

    await goToRepos(page);

    const repoCard = page.locator('.card', { hasText: repoName });
    await expect(repoCard).toBeVisible({ timeout: 5_000 });

    // The card should show "Letzter Sync:" field
    await expect(repoCard.getByText('Letzter Sync:')).toBeVisible();
  });
});
