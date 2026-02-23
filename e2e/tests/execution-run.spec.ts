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

/**
 * Helper: find the Examples repo ID (or the first available repo).
 */
async function getExamplesRepoId(page: Page, token: string): Promise<number> {
  const res = await page.request.get(`${API}/repos`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const repos = await res.json();
  const examples = repos.find((r: any) => r.name === 'Examples');
  return examples?.id ?? repos[0]?.id;
}

test.describe('Execution Run — E2E', () => {
  let token: string;
  let repoId: number;

  test.beforeEach(async ({ page }) => {
    token = await getAuthToken(page);
    repoId = await getExamplesRepoId(page, token);
    await loginAndGoToDashboard(page);
  });

  // ─── API Tests ─────────────────────────────────────────────────────

  test('POST /runs should start a test run', async ({ page }) => {
    const res = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        repository_id: repoId,
        target_path: 'calculator/basic_math.robot',
      },
    });
    expect(res.status()).toBe(201);
    const run = await res.json();
    expect(['pending', 'running']).toContain(run.status);
    expect(run.target_path).toBe('calculator/basic_math.robot');
    expect(run.id).toBeTruthy();
  });

  test('GET /runs/{id} should return run details after completion', async ({ page }) => {
    test.setTimeout(120_000);
    // Create a run first
    const createRes = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: repoId, target_path: 'calculator/basic_math.robot' },
    });
    const run = await createRes.json();

    // Poll until complete (max ~100s — CI queues runs with max_workers=1)
    let detail: any;
    for (let i = 0; i < 50; i++) {
      await page.waitForTimeout(2000);
      const res = await page.request.get(`${API}/runs/${run.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      detail = await res.json();
      if (['passed', 'failed', 'error', 'timeout'].includes(detail.status)) break;
    }

    expect(detail.id).toBe(run.id);
    expect(['passed', 'failed']).toContain(detail.status);
    expect(detail.duration_seconds).toBeGreaterThan(0);
  });

  test('GET /runs/{id}/output should return stdout', async ({ page }) => {
    test.setTimeout(120_000);
    // Create and poll for completion (only accept passed/failed, not error)
    const createRes = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: repoId, target_path: 'calculator/basic_math.robot' },
    });
    const run = await createRes.json();

    let detail: any;
    for (let i = 0; i < 50; i++) {
      await page.waitForTimeout(2000);
      const check = await page.request.get(`${API}/runs/${run.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      detail = await check.json();
      if (['passed', 'failed'].includes(detail.status)) break;
    }

    const res = await page.request.get(`${API}/runs/${run.id}/output`, {
      headers: { Authorization: `Bearer ${token}` },
      params: { stream: 'stdout' },
    });
    expect(res.status()).toBe(200);
    const text = await res.text();
    expect(text).toContain('Basic Math');
  });

  test('GET /runs/{id}/report should return report ID', async ({ page }) => {
    test.setTimeout(120_000);
    // Create and poll for completion (only accept passed/failed for report)
    const createRes = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: repoId, target_path: 'calculator/basic_math.robot' },
    });
    const run = await createRes.json();

    let detail: any;
    for (let i = 0; i < 50; i++) {
      await page.waitForTimeout(2000);
      const check = await page.request.get(`${API}/runs/${run.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      detail = await check.json();
      if (['passed', 'failed'].includes(detail.status)) break;
    }
    // Give extra time for report parsing
    await page.waitForTimeout(3000);

    const res = await page.request.get(`${API}/runs/${run.id}/report`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.report_id).toBeTruthy();
  });

  // ─── UI Tests ─────────────────────────────────────────────────────

  test('UI: can start a run from the execution page', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });

    // Open run dialog
    await page.getByRole('button', { name: /Neuer Run/ }).click();
    await expect(page.getByText('Neuen Run starten')).toBeVisible();

    // Fill form
    await page.locator('select').first().selectOption({ index: 1 }); // first repo
    await page.getByPlaceholder('tests/ oder tests/login.robot').fill('calculator/basic_math.robot');

    // Start run
    await page.getByRole('button', { name: 'Starten' }).click();

    // Handle environment setup dialog if it appears
    const envDialog = page.getByText('Umgebung einrichten?');
    if (await envDialog.isVisible({ timeout: 2000 }).catch(() => false)) {
      await page.getByRole('button', { name: 'Nein, ohne starten' }).click();
    }

    await page.waitForTimeout(2000);

    // Dialog should close
    await expect(page.getByText('Neuen Run starten')).not.toBeVisible({ timeout: 5000 });

    // The runs table should show the new run
    await page.waitForTimeout(1000);
    await expect(page.locator('.data-table')).toBeVisible();
  });

  test('UI: can start a run from explorer and see overlay', async ({ page }) => {
    // Navigate to explorer with the Examples repo
    await page.goto(`/explorer/${repoId}`);
    await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(1000);

    // Expand calculator directory
    const calcDir = page.locator('.tree-node .node-name', { hasText: /^calculator$/ });
    await calcDir.click();
    await page.waitForTimeout(500);

    // Hover over basic_math.robot to see action buttons
    const robotFile = page.locator('.tree-node', { hasText: 'basic_math.robot' });
    await robotFile.hover();
    await page.waitForTimeout(300);

    // Click the run button (▶)
    const runBtn = robotFile.locator('.node-action-btn.run');
    await runBtn.click();
    await page.waitForTimeout(1000);

    // Handle environment setup dialog if it appears
    const envDialog = page.getByText('Umgebung einrichten?');
    if (await envDialog.isVisible({ timeout: 2000 }).catch(() => false)) {
      await page.getByRole('button', { name: 'Nein, ohne starten' }).click();
      await page.waitForTimeout(1000);
    }

    // Overlay should appear
    await expect(page.getByText('Testlauf gestartet')).toBeVisible({ timeout: 5000 });
    // File name appears in the run overlay text
    await expect(page.locator('.run-overlay-success')).toContainText('basic_math.robot');

    // Should have "Zur Ausführung" button
    await expect(page.getByRole('button', { name: 'Zur Ausführung' })).toBeVisible();

    // Close overlay
    await page.getByRole('button', { name: 'Schließen' }).click();
  });

  test('UI: execution page shows Output button for completed runs', async ({ page }) => {
    test.setTimeout(120_000);

    // Create a run and wait for it to complete
    const createRes = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: repoId, target_path: 'calculator/basic_math.robot' },
    });
    const run = await createRes.json();

    // Poll this specific run until it reaches a terminal state
    for (let i = 0; i < 50; i++) {
      await page.waitForTimeout(2000);
      const res = await page.request.get(`${API}/runs/${run.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const detail = await res.json();
      if (['passed', 'failed', 'error'].includes(detail.status)) break;
    }

    // Go to execution page
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(2000);

    // Click on the first (completed) run row to open the detail panel
    const firstRow = page.locator('.data-table tbody tr').first();
    await expect(firstRow).toBeVisible({ timeout: 5000 });
    await firstRow.click();
    await page.waitForTimeout(1000);

    // The Output button is in the RunDetailPanel (appears after clicking a row)
    const outputBtn = page.getByRole('button', { name: 'Output' }).first();
    await expect(outputBtn).toBeVisible({ timeout: 5000 });

    // Click it
    await outputBtn.click();
    await page.waitForTimeout(500);

    // Output modal should appear
    await expect(page.getByText(/Output — Run/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'stdout' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'stderr' })).toBeVisible();
  });
});
