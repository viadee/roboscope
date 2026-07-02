/**
 * Debug workflow — the full "run fails → inspect → fix → re-run green" loop.
 *
 * Covers the debugging gap from the use-case audit (2026-07-02):
 *  - a failed run surfaces its failing test in the run detail panel,
 *  - the user identifies the needed change, fixes the test in the editor
 *    (Code tab), saves,
 *  - retries from the UI and the run turns green,
 *  - a RUNNING test can be inspected and cancelled from the UI.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const BROKEN_ROBOT = `*** Test Cases ***
Passing Test
    Log    ok

Broken Test
    Should Be Equal As Integers    1    2
`;

const FIXED_ROBOT = `*** Test Cases ***
Passing Test
    Log    ok

Broken Test
    Should Be Equal As Integers    1    1
`;

const SLOW_ROBOT = `*** Test Cases ***
Slow Test
    Sleep    90s

Trivial Test
    Log    quick
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

async function cancelAllRuns(page: Page, token: string): Promise<void> {
  await page.request.post(`${API}/runs/cancel-all`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await page.waitForTimeout(2000);
}

async function getRun(page: Page, token: string, runId: number): Promise<any> {
  const res = await page.request.get(`${API}/runs/${runId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return await res.json();
}

async function pollRunToCompletion(page: Page, token: string, runId: number, maxIterations = 110): Promise<any> {
  let detail: any;
  for (let i = 0; i < maxIterations; i++) {
    await page.waitForTimeout(2000);
    detail = await getRun(page, token, runId);
    if (['passed', 'failed', 'error', 'timeout', 'cancelled'].includes(detail.status)) return detail;
  }
  return detail;
}

async function pollRunUntilRunning(page: Page, token: string, runId: number, maxIterations = 110): Promise<any> {
  let detail: any;
  for (let i = 0; i < maxIterations; i++) {
    await page.waitForTimeout(2000);
    detail = await getRun(page, token, runId);
    if (detail.status !== 'pending') return detail;
  }
  return detail;
}

test.describe.serial('Debug workflow — fail, inspect, fix, re-run', () => {
  let token: string;
  let repoId: number;
  let failedRunId: number;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    token = await getAuthToken(page);
    const stamp = Date.now();
    const res = await page.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: `debug-wf-e2e-${stamp}`, repo_type: 'local', local_path: `/tmp/roboscope-debug-wf-${stamp}` },
    });
    expect(res.status()).toBe(201);
    repoId = (await res.json()).id as number;
    for (const [path, content] of [
      ['tests/debug.robot', BROKEN_ROBOT],
      ['tests/slow.robot', SLOW_ROBOT],
    ] as const) {
      const fr = await page.request.post(`${API}/explorer/${repoId}/file`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { path, content },
      });
      expect(fr.status()).toBeLessThan(300);
    }
    await page.close();
  });

  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    const t = await getAuthToken(page);
    await cancelAllRuns(page, t);
    await page.request.delete(`${API}/repos/${repoId}`, { headers: { Authorization: `Bearer ${t}` } });
    await page.close();
  });

  test('failed run surfaces the failing test in the detail panel', async ({ page }) => {
    test.setTimeout(300_000);
    await cancelAllRuns(page, token);

    const res = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: repoId, target_path: 'tests/debug.robot' },
    });
    expect(res.status()).toBe(201);
    failedRunId = (await res.json()).id as number;
    const detail = await pollRunToCompletion(page, token, failedRunId);
    expect(detail.status).toBe('failed');

    // Inspect in the UI
    await loginAndGoToDashboard(page);
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });

    const row = page.locator('.data-table tbody tr', { hasText: 'debug.robot' }).first();
    await expect(row).toBeVisible({ timeout: 10_000 });
    await row.click();

    // The report identifies WHICH test needs a change — the heart of the
    // debugging journey: the user learns it's "Broken Test", not the suite.
    await expect(page.locator('.failed-tests-section')).toBeVisible({ timeout: 20_000 });
    await expect(page.locator('.failed-tests-section')).toContainText('Broken Test');
  });

  test('user fixes the test in the Code editor and the retried run turns green', async ({ page }) => {
    test.setTimeout(400_000);
    await loginAndGoToDashboard(page);

    // Open the broken file in the editor
    await page.goto(`/explorer/${repoId}`);
    await expect(page.locator('h1', { hasText: 'Explorer' })).toBeVisible({ timeout: 10_000 });
    const testsFolder = page.locator('text=/^tests$/').first();
    await expect(testsFolder).toBeVisible({ timeout: 10_000 });
    const fileRow = page.locator('text=debug.robot').first();
    if (!(await fileRow.isVisible().catch(() => false))) await testsFolder.click();
    await expect(fileRow).toBeVisible({ timeout: 8_000 });
    await fileRow.click();

    // Fix it on the Code tab: replace the whole buffer with the corrected suite
    await page.locator('button.tab-btn', { hasText: /^Code$/ }).first().click();
    const code = page.locator('.cm-content');
    await expect(code).toBeVisible({ timeout: 8_000 });
    await code.click();
    await page.keyboard.press('ControlOrMeta+A');
    await page.keyboard.insertText(FIXED_ROBOT);

    // Save via the editor toolbar and verify on disk
    const saveBtn = page.getByRole('button', { name: /Speichern|Save/ }).first();
    await expect(saveBtn).toBeVisible({ timeout: 8_000 });
    await saveBtn.click();
    await expect(page.locator('.unsaved-badge')).toHaveCount(0, { timeout: 8_000 });
    await expect(async () => {
      const res = await page.request.get(`${API}/explorer/${repoId}/file`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { path: 'tests/debug.robot' },
      });
      const body = await res.json();
      expect(body.content).toContain('Should Be Equal As Integers    1    1');
    }).toPass({ timeout: 10_000 });

    // Retry the failed run from the UI (detail panel button)
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });
    const row = page.locator('.data-table tbody tr', { hasText: 'debug.robot' }).first();
    await expect(row).toBeVisible({ timeout: 10_000 });
    await row.click();
    await page.getByRole('button', { name: 'Retry' }).first().click();
    await page.waitForTimeout(2000);

    // The retry created a NEW run for the same target — find and poll it
    const listRes = await page.request.get(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const listBody = await listRes.json();
    const runs: any[] = Array.isArray(listBody) ? listBody : listBody.items ?? listBody.runs ?? [];
    const newest = runs
      .filter((r) => r.target_path === 'tests/debug.robot' && r.id !== failedRunId)
      .sort((a, b) => b.id - a.id)[0];
    expect(newest, 'retry should have created a new run').toBeTruthy();

    const detail = await pollRunToCompletion(page, token, newest.id);
    expect(detail.status).toBe('passed');
  });

  test('a running test can be inspected and cancelled from the UI', async ({ page }) => {
    test.setTimeout(300_000);

    const res = await page.request.post(`${API}/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { repository_id: repoId, target_path: 'tests/slow.robot' },
    });
    expect(res.status()).toBe(201);
    const runId = (await res.json()).id as number;

    // Wait until it leaves the queue and actually runs
    const running = await pollRunUntilRunning(page, token, runId);
    expect(running.status).toBe('running');

    await loginAndGoToDashboard(page);
    await page.goto('/runs');
    await expect(page.locator('h1', { hasText: 'Ausführung' })).toBeVisible({ timeout: 10_000 });
    const row = page.locator('.data-table tbody tr', { hasText: 'slow.robot' }).first();
    await expect(row).toBeVisible({ timeout: 10_000 });
    await row.click();

    // Live monitoring: the panel offers Abbrechen while the run is active
    const cancelBtn = page.getByRole('button', { name: 'Abbrechen' }).first();
    await expect(cancelBtn).toBeVisible({ timeout: 10_000 });
    await cancelBtn.click();

    // The run reaches the cancelled terminal state
    const detail = await pollRunToCompletion(page, token, runId, 30);
    expect(detail.status).toBe('cancelled');
  });
});
