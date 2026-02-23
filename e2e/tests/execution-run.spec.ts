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

/**
 * Helper: cancel all running/pending runs and wait for the executor to drain.
 */
async function cancelAllRuns(page: Page, token: string): Promise<void> {
  await page.request.post(`${API}/runs/cancel-all`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  // Give the executor a moment to process cancellations
  await page.waitForTimeout(2000);
}

/**
 * Helper: poll a run until it reaches a terminal state.
 * Returns the run detail object.
 */
async function pollRunToCompletion(
  page: Page,
  token: string,
  runId: number,
  maxIterations = 60,
): Promise<any> {
  let detail: any;
  for (let i = 0; i < maxIterations; i++) {
    await page.waitForTimeout(2000);
    const res = await page.request.get(`${API}/runs/${runId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    detail = await res.json();
    if (['passed', 'failed', 'error', 'timeout', 'cancelled'].includes(detail.status)) {
      return detail;
    }
  }
  return detail;
}

// ─── API Tests (serial — share a single run to avoid executor queue buildup) ──

test.describe.serial('Execution Run — API Tests', () => {
  let token: string;
  let repoId: number;
  let runId: number;
  let completedDetail: any;

  test('POST /runs should start a test run', async ({ page }) => {
    test.setTimeout(180_000);
    token = await getAuthToken(page);
    repoId = await getExamplesRepoId(page, token);

    // Cancel any leftover runs from previous specs
    await cancelAllRuns(page, token);

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
    runId = run.id;

    // Poll until the run completes (shared across subsequent tests)
    completedDetail = await pollRunToCompletion(page, token, runId);
    expect(['passed', 'failed']).toContain(completedDetail.status);
  });

  test('GET /runs/{id} should return run details after completion', async ({ page }) => {
    // Re-fetch to prove the endpoint works (run already completed above)
    const res = await page.request.get(`${API}/runs/${runId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const detail = await res.json();

    expect(detail.id).toBe(runId);
    expect(['passed', 'failed']).toContain(detail.status);
    expect(detail.duration_seconds).toBeGreaterThan(0);
  });

  test('GET /runs/{id}/output should return stdout', async ({ page }) => {
    const res = await page.request.get(`${API}/runs/${runId}/output`, {
      headers: { Authorization: `Bearer ${token}` },
      params: { stream: 'stdout' },
    });
    expect(res.status()).toBe(200);
    const text = await res.text();
    expect(text).toContain('Basic Math');
  });

  test('GET /runs/{id}/report should return report ID', async ({ page }) => {
    // Give extra time for report parsing
    await page.waitForTimeout(3000);

    const res = await page.request.get(`${API}/runs/${runId}/report`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.report_id).toBeTruthy();
  });
});

// ─── UI Tests ─────────────────────────────────────────────────────────────────

test.describe('Execution Run — UI Tests', () => {
  let token: string;
  let repoId: number;

  test.beforeEach(async ({ page }) => {
    token = await getAuthToken(page);
    repoId = await getExamplesRepoId(page, token);
    await loginAndGoToDashboard(page);
  });

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
    test.setTimeout(180_000);

    // Cancel any queued runs to free the executor
    await cancelAllRuns(page, token);

    // Create a run and poll until it completes
    const createRes = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: repoId, target_path: 'calculator/basic_math.robot' },
    });
    const run = await createRes.json();
    await pollRunToCompletion(page, token, run.id);

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
