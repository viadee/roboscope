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

test.describe('Execution Run — E2E', () => {
  let token: string;

  test.beforeEach(async ({ page }) => {
    token = await getAuthToken(page);
    await loginAndGoToDashboard(page);
  });

  // ─── API Tests ─────────────────────────────────────────────────────

  test('POST /runs should start a test run', async ({ page }) => {
    const res = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        repository_id: 1,
        target_path: 'tests/basic_tests.robot',
      },
    });
    expect(res.status()).toBe(201);
    const run = await res.json();
    expect(['pending', 'running']).toContain(run.status);
    expect(run.target_path).toBe('tests/basic_tests.robot');
    expect(run.id).toBeTruthy();
  });

  test('GET /runs/{id} should return run details after completion', async ({ page }) => {
    // Create a run first
    const createRes = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: 1, target_path: 'tests/basic_tests.robot' },
    });
    const run = await createRes.json();

    // Poll until complete (max 30s)
    let detail: any;
    for (let i = 0; i < 15; i++) {
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
    // Create and poll for completion
    const createRes = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: 1, target_path: 'tests/basic_tests.robot' },
    });
    const run = await createRes.json();

    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(2000);
      const check = await page.request.get(`${API}/runs/${run.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await check.json();
      if (['passed', 'failed', 'error'].includes(d.status)) break;
    }

    const res = await page.request.get(`${API}/runs/${run.id}/output`, {
      headers: { Authorization: `Bearer ${token}` },
      params: { stream: 'stdout' },
    });
    expect(res.status()).toBe(200);
    const text = await res.text();
    expect(text).toContain('Basic Tests');
  });

  test('GET /runs/{id}/report should return report ID', async ({ page }) => {
    // Create and poll for completion
    const createRes = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: 1, target_path: 'tests/basic_tests.robot' },
    });
    const run = await createRes.json();

    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(2000);
      const check = await page.request.get(`${API}/runs/${run.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await check.json();
      if (['passed', 'failed', 'error'].includes(d.status)) break;
    }
    // Give an extra moment for report parsing
    await page.waitForTimeout(2000);

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
    await page.getByPlaceholder('tests/ oder tests/login.robot').fill('tests/basic_tests.robot');

    // Start run
    await page.getByRole('button', { name: 'Starten' }).click();
    await page.waitForTimeout(2000);

    // Dialog should close
    await expect(page.getByText('Neuen Run starten')).not.toBeVisible({ timeout: 5000 });

    // The runs table should show the new run
    await page.waitForTimeout(1000);
    await expect(page.locator('.data-table')).toBeVisible();
  });

  test('UI: can start a run from explorer and see overlay', async ({ page }) => {
    // Navigate to explorer with repo 1
    await page.goto('/explorer/1');
    await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(1000);

    // Expand tests directory
    const testsDir = page.locator('.tree-node .node-name', { hasText: /^tests$/ });
    await testsDir.click();
    await page.waitForTimeout(500);

    // Hover over basic_tests.robot to see action buttons
    const robotFile = page.locator('.tree-node', { hasText: 'basic_tests.robot' });
    await robotFile.hover();
    await page.waitForTimeout(300);

    // Click the run button (▶)
    const runBtn = robotFile.locator('.node-action-btn.run');
    await runBtn.click();
    await page.waitForTimeout(1000);

    // Overlay should appear
    await expect(page.getByText('Testlauf gestartet')).toBeVisible({ timeout: 5000 });
    // File name appears in both tree and overlay - use the modal context
    await expect(page.locator('.modal-body strong', { hasText: 'basic_tests.robot' })).toBeVisible();

    // Should have "Zur Ausführung" button
    await expect(page.getByRole('button', { name: 'Zur Ausführung' })).toBeVisible();

    // Close overlay
    await page.getByRole('button', { name: 'Schließen' }).click();
  });

  test('UI: execution page shows Output button for completed runs', async ({ page }) => {
    // First ensure there's a completed run
    await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: 1, target_path: 'tests/basic_tests.robot' },
    });
    await page.waitForTimeout(8000);

    // Go to execution page
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(2000);

    // There should be at least one completed run with an Output button
    const outputBtn = page.getByRole('button', { name: 'Output' }).first();
    await expect(outputBtn).toBeVisible({ timeout: 5000 });

    // Click it
    await outputBtn.click();
    await page.waitForTimeout(500);

    // Output modal should appear
    await expect(page.getByText(/Output — Run/)).toBeVisible();
    await expect(page.getByText('stdout')).toBeVisible();
    await expect(page.getByText('stderr')).toBeVisible();

    // Content should show test output
    const outputContent = page.locator('.output-content');
    await expect(outputContent).toBeVisible();
  });
});
