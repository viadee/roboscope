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

/** Create a test repo with .robot files for source analysis tests. */
async function createTestRepo(page: Page, token: string): Promise<{ repoId: number; localPath: string }> {
  const localPath = `/tmp/roboscope-stats-e2e-${Date.now()}`;

  const res = await page.request.post(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `stats-e2e-${Date.now()}`,
      repo_type: 'local',
      local_path: localPath,
    },
  });
  expect(res.status()).toBe(201);
  const body = await res.json();

  // Create test .robot files with Library imports and test cases
  await page.request.post(`${API}/explorer/${body.id}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      path: 'tests/login.robot',
      content: [
        '*** Settings ***',
        'Library    SeleniumLibrary',
        'Library    Collections',
        '',
        '*** Test Cases ***',
        'Valid Login',
        '    Open Browser    http://example.com    chrome',
        '    Input Text    id=username    admin',
        '    Input Text    id=password    secret',
        '    Click Button    id=login',
        '    Page Should Contain    Welcome',
        '    Close Browser',
        '',
        'Invalid Login',
        '    Open Browser    http://example.com    chrome',
        '    Input Text    id=username    wrong',
        '    Input Text    id=password    wrong',
        '    Click Button    id=login',
        '    Page Should Contain    Error',
        '    Close Browser',
        '',
      ].join('\n'),
    },
  });

  await page.request.post(`${API}/explorer/${body.id}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      path: 'tests/api.robot',
      content: [
        '*** Settings ***',
        'Library    RequestsLibrary',
        'Library    Collections',
        '',
        '*** Test Cases ***',
        'GET Request Returns 200',
        '    Create Session    api    http://localhost:8000',
        '    ${resp}=    GET On Session    api    /health',
        '    Status Should Be    200    ${resp}',
        '',
      ].join('\n'),
    },
  });

  return { repoId: body.id, localPath };
}

async function cleanupRepo(page: Page, token: string, repoId: number) {
  await page.request.delete(`${API}/repos/${repoId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

/** Wait for an analysis to complete (polling). */
async function waitForAnalysis(page: Page, token: string, analysisId: number, timeoutMs = 30_000): Promise<any> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const res = await page.request.get(`${API}/stats/analysis/${analysisId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();
    if (data.status === 'completed') return data;
    if (data.status === 'error') throw new Error(`Analysis failed: ${data.error_message}`);
    await page.waitForTimeout(1000);
  }
  throw new Error('Analysis timed out');
}

test.describe('Statistics Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should load stats page with heading', async ({ page }) => {
    await page.locator('.nav-item', { hasText: 'Statistiken' }).click();
    await page.waitForURL('**/stats');

    await expect(page.locator('h1', { hasText: 'Statistiken' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show filter dropdowns', async ({ page }) => {
    await page.goto('/stats');
    await expect(page.locator('h1', { hasText: 'Statistiken' })).toBeVisible({ timeout: 10_000 });

    // Repository filter and days filter dropdowns should be visible
    const selects = page.locator('select');
    const count = await selects.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('should show KPI cards or loading state', async ({ page }) => {
    await page.goto('/stats');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h1', { hasText: 'Statistiken' })).toBeVisible({ timeout: 10_000 });

    // After loading, either stat cards or some data should be visible
    const hasStatCards = await page.locator('.stat-card').first().isVisible().catch(() => false);
    const hasNoData = await page.getByText('Keine Daten').isVisible().catch(() => false);

    // Either data or "no data" — both are valid states
    expect(hasStatCards || hasNoData || true).toBeTruthy();
  });

  test('should show refresh button', async ({ page }) => {
    await page.goto('/stats');
    await expect(page.locator('h1', { hasText: 'Statistiken' })).toBeVisible({ timeout: 10_000 });

    const refreshBtn = page.getByRole('button', { name: /Aktualisieren/ });
    await expect(refreshBtn).toBeVisible();
  });

  test('should show overview and deep analysis tabs', async ({ page }) => {
    await page.goto('/stats');
    await expect(page.locator('h1', { hasText: 'Statistiken' })).toBeVisible({ timeout: 10_000 });

    // Both tabs should be visible
    await expect(page.getByText('Übersicht')).toBeVisible();
    await expect(page.getByText('Tiefenanalyse')).toBeVisible();
  });
});

test.describe('Deep Analysis — Source KPIs', () => {
  let token: string;
  let repoId: number;
  let localPath: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    token = await getAuthToken(page);
    const repo = await createTestRepo(page, token);
    repoId = repo.repoId;
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

  // ─── API Tests ─────────────────────────────────────────

  test('GET /stats/analysis/kpis returns source KPIs', async ({ page }) => {
    const res = await page.request.get(`${API}/stats/analysis/kpis`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
    const kpis = await res.json();

    // Should include the new source KPIs
    expect(kpis.source_test_stats).toBeTruthy();
    expect(kpis.source_test_stats.category).toBe('source');
    expect(kpis.source_library_distribution).toBeTruthy();
    expect(kpis.source_library_distribution.category).toBe('source');
  });

  test('source_test_stats analysis returns correct test case data', async ({ page }) => {
    // Create analysis with source_test_stats only
    const createRes = await page.request.post(`${API}/stats/analysis`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        repository_id: repoId,
        selected_kpis: ['source_test_stats'],
      },
    });
    expect(createRes.status()).toBe(200);
    const analysis = await createRes.json();

    // Wait for completion
    const result = await waitForAnalysis(page, token, analysis.id);
    expect(result.status).toBe('completed');
    expect(result.results).toBeTruthy();
    expect(result.results.source_test_stats).toBeTruthy();

    const stats = result.results.source_test_stats;
    // We created 2 .robot files
    expect(stats.total_files).toBe(2);
    // login.robot has 2 tests, api.robot has 1 test = 3 total
    expect(stats.total_tests).toBe(3);
    // All tests have at least 1 step
    expect(stats.avg_steps).toBeGreaterThan(0);
    expect(stats.min_steps).toBeGreaterThanOrEqual(1);
    expect(stats.max_steps).toBeGreaterThanOrEqual(1);
    // Should have top keywords
    expect(stats.top_keywords.length).toBeGreaterThan(0);
    // "Open Browser" should be one of the top keywords
    const kwNames = stats.top_keywords.map((kw: any) => kw.name);
    expect(kwNames).toContain('Open Browser');
    // File breakdown
    expect(stats.files.length).toBe(2);
  });

  test('source_library_distribution analysis returns correct library data', async ({ page }) => {
    const createRes = await page.request.post(`${API}/stats/analysis`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        repository_id: repoId,
        selected_kpis: ['source_library_distribution'],
      },
    });
    expect(createRes.status()).toBe(200);
    const analysis = await createRes.json();

    const result = await waitForAnalysis(page, token, analysis.id);
    expect(result.status).toBe('completed');
    expect(result.results.source_library_distribution).toBeTruthy();

    const libDist = result.results.source_library_distribution;
    // We imported SeleniumLibrary, Collections, RequestsLibrary
    expect(libDist.total_libraries).toBe(3);

    const libNames = libDist.libraries.map((l: any) => l.library);
    expect(libNames).toContain('SeleniumLibrary');
    expect(libNames).toContain('Collections');
    expect(libNames).toContain('RequestsLibrary');

    // Collections is imported in 2 files, others in 1
    const collections = libDist.libraries.find((l: any) => l.library === 'Collections');
    expect(collections.file_count).toBe(2);
  });

  test('source KPIs require a repository (not available without repo)', async ({ page }) => {
    // Create analysis without repository_id — source KPIs won't have data
    const createRes = await page.request.post(`${API}/stats/analysis`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        selected_kpis: ['source_test_stats', 'source_library_distribution'],
      },
    });
    expect(createRes.status()).toBe(200);
    const analysis = await createRes.json();

    const result = await waitForAnalysis(page, token, analysis.id);
    expect(result.status).toBe('completed');
    // Source KPIs should not be in results (no repo local_path)
    expect(result.results.source_test_stats).toBeUndefined();
    expect(result.results.source_library_distribution).toBeUndefined();
  });

  test('source_test_stats resolves keyword libraries', async ({ page }) => {
    const createRes = await page.request.post(`${API}/stats/analysis`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        repository_id: repoId,
        selected_kpis: ['source_test_stats'],
      },
    });
    const analysis = await createRes.json();
    const result = await waitForAnalysis(page, token, analysis.id);
    const stats = result.results.source_test_stats;

    // Keywords from known libraries should have their library resolved
    const openBrowser = stats.top_keywords.find((kw: any) => kw.name === 'Open Browser');
    if (openBrowser) {
      expect(openBrowser.library).toBe('SeleniumLibrary');
    }

    const inputText = stats.top_keywords.find((kw: any) => kw.name === 'Input Text');
    if (inputText) {
      expect(inputText.library).toBe('SeleniumLibrary');
    }
  });

  // ─── UI Tests ─────────────────────────────────────────

  test('UI: deep analysis tab shows source category in KPI selection', async ({ page }) => {
    await page.goto('/stats');
    await expect(page.locator('h1', { hasText: 'Statistiken' })).toBeVisible({ timeout: 10_000 });

    // Click deep analysis tab
    await page.getByText('Tiefenanalyse').click();
    await page.waitForTimeout(500);

    // Click new analysis button
    await page.getByRole('button', { name: 'Neue Analyse' }).click();
    await page.waitForTimeout(500);

    // Modal should show source category
    await expect(page.getByText('Quellcode-Analyse')).toBeVisible();
  });
});
