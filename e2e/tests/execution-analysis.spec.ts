import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

/**
 * E2E tests for AI Failure Analysis in the RunDetailPanel (Execution page).
 *
 * These tests verify the analysis card is correctly displayed when viewing
 * a completed run with failed tests from the execution page, including:
 * - Analysis card visibility with/without providers and failures
 * - Analyze button click → loading → completed result
 * - Error handling (failed jobs, API errors)
 * - Provider fallback (non-default provider still works)
 */

// --- Mock data ---

const mockProvider = {
  id: 1,
  name: 'Test Provider',
  provider_type: 'openai',
  api_base_url: null,
  has_api_key: true,
  model_name: 'gpt-4o',
  temperature: 0.3,
  max_tokens: 4096,
  is_default: false, // NOT default — tests the fallback logic
  created_by: 1,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
};

const mockFailedRun = {
  id: 42,
  repository_id: 1,
  environment_id: null,
  run_type: 'manual',
  runner_type: 'subprocess',
  status: 'failed',
  target_path: 'tests/checkout.robot',
  branch: 'main',
  tags_include: null,
  tags_exclude: null,
  parallel: false,
  retry_count: 0,
  max_retries: 0,
  timeout_seconds: 3600,
  celery_task_id: null,
  started_at: '2026-01-15T10:00:00',
  finished_at: '2026-01-15T10:00:12',
  duration_seconds: 12.5,
  triggered_by: 1,
  error_message: null,
  created_at: '2026-01-15T10:00:00',
};

const mockPassedRun = {
  ...mockFailedRun,
  id: 43,
  status: 'passed',
  target_path: 'tests/login.robot',
};

const mockReport = {
  report: {
    id: 100,
    execution_run_id: 42,
    total_tests: 3,
    passed_tests: 1,
    failed_tests: 2,
    skipped_tests: 0,
    total_duration_seconds: 12.5,
    created_at: '2026-01-15T10:00:12',
  },
  test_results: [
    { id: 1, report_id: 100, suite_name: 'Checkout Suite', test_name: 'Add to Cart', status: 'FAIL', duration_seconds: 3.2, error_message: "No keyword with name 'Click Element' found.", tags: 'regression', start_time: null, end_time: null },
    { id: 2, report_id: 100, suite_name: 'Checkout Suite', test_name: 'Payment Flow', status: 'FAIL', duration_seconds: 3.9, error_message: 'Timeout waiting for payment gateway', tags: null, start_time: null, end_time: null },
    { id: 3, report_id: 100, suite_name: 'Checkout Suite', test_name: 'View Cart', status: 'PASS', duration_seconds: 2.1, error_message: null, tags: null, start_time: null, end_time: null },
  ],
};

const mockReportAllPassed = {
  report: {
    id: 101,
    execution_run_id: 43,
    total_tests: 2,
    passed_tests: 2,
    failed_tests: 0,
    skipped_tests: 0,
    total_duration_seconds: 5.0,
    created_at: '2026-01-15T10:00:05',
  },
  test_results: [
    { id: 10, report_id: 101, suite_name: 'Login Suite', test_name: 'Valid Login', status: 'PASS', duration_seconds: 2.5, error_message: null, tags: null, start_time: null, end_time: null },
    { id: 11, report_id: 101, suite_name: 'Login Suite', test_name: 'Invalid Login', status: 'PASS', duration_seconds: 2.5, error_message: null, tags: null, start_time: null, end_time: null },
  ],
};

const mockAnalyzeJobPending = {
  id: 99,
  job_type: 'analyze',
  status: 'pending',
  repository_id: 1,
  provider_id: 1,
  report_id: 100,
  spec_path: '',
  target_path: null,
  result_preview: null,
  error_message: null,
  token_usage: null,
  triggered_by: 1,
  started_at: null,
  completed_at: null,
  created_at: '2026-01-15T10:01:00',
};

const mockAnalyzeJobCompleted = {
  ...mockAnalyzeJobPending,
  status: 'completed',
  result_preview: '## Root Cause Analysis\n\n### 1. Add to Cart\n- **Priority**: HIGH\n- No keyword with name \'Click Element\' found — SeleniumLibrary may not be imported.\n\n### 2. Payment Flow\n- **Priority**: CRITICAL\n- Timeout waiting for payment gateway — service may be down.\n\n## Action List\n1. Add SeleniumLibrary to Settings\n2. Check payment gateway availability',
  token_usage: 850,
  started_at: '2026-01-15T10:01:01',
  completed_at: '2026-01-15T10:01:10',
};

const mockAnalyzeJobFailed = {
  ...mockAnalyzeJobPending,
  status: 'failed',
  error_message: 'LLM API returned 429: rate limited',
  started_at: '2026-01-15T10:01:01',
  completed_at: '2026-01-15T10:01:02',
};

const mockXmlData = {
  suites: [],
  statistics: { total: { 'All Tests': { pass: 1, fail: 2, skip: 0 } } },
  generated: '20260115 10:00:12.500',
};

// --- Helpers ---

/**
 * Set up all API mocks needed for the execution page with a single failed run.
 */
async function setupExecutionMocks(page: Page, opts: { providers?: object[]; runs?: object[] } = {}) {
  const runs = opts.runs || [mockFailedRun];
  const providers = opts.providers || [mockProvider];

  // Runs list
  await page.route('**/api/v1/runs?*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: runs, total: runs.length, page: 1, page_size: 20 }),
    });
  });

  // Single run detail
  for (const run of runs) {
    const r = run as typeof mockFailedRun;
    await page.route(`**/api/v1/runs/${r.id}`, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(r),
        });
      } else {
        await route.fallback();
      }
    });
  }

  // Run → Report mapping
  await page.route('**/api/v1/runs/42/report', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ report_id: 100 }),
    });
  });

  await page.route('**/api/v1/runs/43/report', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ report_id: 101 }),
    });
  });

  // Report details
  await page.route('**/api/v1/reports/100', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockReport),
    });
  });

  await page.route('**/api/v1/reports/101', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockReportAllPassed),
    });
  });

  await page.route('**/api/v1/reports/100/xml-data', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockXmlData),
    });
  });

  await page.route('**/api/v1/reports/101/xml-data', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockXmlData),
    });
  });

  await page.route('**/api/v1/reports/*/html*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body></body></html>' });
  });

  // AI providers
  await page.route('**/api/v1/ai/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(providers),
    });
  });

  // Repos (needed by ExecutionView)
  await page.route('**/api/v1/repos', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: 1, name: 'Test Repo', local_path: '/tmp/repo', is_local: true, default_branch: 'main', environment_id: null }]),
    });
  });

  // Environments (needed by ExecutionView)
  await page.route('**/api/v1/environments', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  // Schedules (needed by ExecutionView)
  await page.route('**/api/v1/schedules', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
}

test.describe('AI Analysis in RunDetailPanel (Execution Page)', () => {

  test('should show analysis card with Analyze button for a failed run', async ({ page }) => {
    await setupExecutionMocks(page);
    await loginAndGoToDashboard(page);
    await page.goto('/runs');
    await page.waitForLoadState('networkidle');

    // Click on the failed run row
    const runRow = page.locator('.data-table tbody tr').first();
    await expect(runRow).toBeVisible({ timeout: 5_000 });
    await runRow.click();

    // Wait for RunDetailPanel to load report
    await expect(page.locator('.run-detail-panel')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.kpi-row')).toBeVisible({ timeout: 5_000 });

    // Scroll to analysis card
    const analysisCard = page.locator('.analysis-card');
    await analysisCard.scrollIntoViewIfNeeded();
    await expect(analysisCard).toBeVisible();

    // Analyze button should be visible
    await expect(page.locator('.analysis-initial button')).toBeVisible();
  });

  test('should NOT show analysis card for a passed run (no failures)', async ({ page }) => {
    await setupExecutionMocks(page, { runs: [mockPassedRun] });
    await loginAndGoToDashboard(page);
    await page.goto('/runs');
    await page.waitForLoadState('networkidle');

    // Click on the passed run row
    const runRow = page.locator('.data-table tbody tr').first();
    await expect(runRow).toBeVisible({ timeout: 5_000 });
    await runRow.click();

    // Wait for RunDetailPanel to load
    await expect(page.locator('.run-detail-panel')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.kpi-row')).toBeVisible({ timeout: 5_000 });

    // Analysis card should NOT appear (all tests passed)
    await expect(page.locator('.analysis-card')).not.toBeVisible();
  });

  test('should show no-provider hint when no AI provider is configured', async ({ page }) => {
    await setupExecutionMocks(page, { providers: [] });
    await loginAndGoToDashboard(page);
    await page.goto('/runs');
    await page.waitForLoadState('networkidle');

    // Click on the failed run row
    await page.locator('.data-table tbody tr').first().click();
    await expect(page.locator('.run-detail-panel')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.kpi-row')).toBeVisible({ timeout: 5_000 });

    // Analysis card should show no-provider hint
    const analysisCard = page.locator('.analysis-card');
    await analysisCard.scrollIntoViewIfNeeded();
    await expect(analysisCard).toBeVisible();
    await expect(page.locator('.analysis-hint')).toBeVisible();
  });

  test('should show loading → completed analysis result', async ({ page }) => {
    await setupExecutionMocks(page);

    // POST /ai/analyze returns pending job
    await page.route('**/api/v1/ai/analyze', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAnalyzeJobPending),
      });
    });

    // Poll: first returns running, second returns completed
    let pollCount = 0;
    await page.route('**/api/v1/ai/status/99', async (route) => {
      pollCount++;
      if (pollCount <= 1) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...mockAnalyzeJobPending, status: 'running' }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockAnalyzeJobCompleted),
        });
      }
    });

    await loginAndGoToDashboard(page);
    await page.goto('/runs');
    await page.waitForLoadState('networkidle');

    // Click run row and scroll to analysis
    await page.locator('.data-table tbody tr').first().click();
    await expect(page.locator('.kpi-row')).toBeVisible({ timeout: 5_000 });

    const analyzeBtn = page.locator('.analysis-initial button');
    await analyzeBtn.scrollIntoViewIfNeeded();
    await analyzeBtn.click();

    // Loading state
    await expect(page.locator('.analysis-loading')).toBeVisible();

    // Wait for completed result
    await expect(page.locator('.analysis-result')).toBeVisible({ timeout: 10_000 });

    // Verify markdown content rendered
    await expect(page.locator('.analysis-content')).toContainText('Root Cause Analysis');
    await expect(page.locator('.analysis-content')).toContainText('Add to Cart');
    await expect(page.locator('.analysis-content')).toContainText('SeleniumLibrary');

    // Token count and re-analyze button
    await expect(page.locator('.analysis-footer')).toContainText('850');
    await expect(page.locator('.analysis-footer button')).toBeVisible();
  });

  test('should show error state when analysis job fails', async ({ page }) => {
    await setupExecutionMocks(page);

    await page.route('**/api/v1/ai/analyze', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAnalyzeJobPending),
      });
    });

    await page.route('**/api/v1/ai/status/99', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAnalyzeJobFailed),
      });
    });

    await loginAndGoToDashboard(page);
    await page.goto('/runs');
    await page.waitForLoadState('networkidle');

    await page.locator('.data-table tbody tr').first().click();
    await expect(page.locator('.kpi-row')).toBeVisible({ timeout: 5_000 });

    const analyzeBtn = page.locator('.analysis-initial button');
    await analyzeBtn.scrollIntoViewIfNeeded();
    await analyzeBtn.click();

    // Error state with rate limit message
    await expect(page.locator('.analysis-error')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.analysis-error')).toContainText('rate limited');

    // Retry button
    await expect(page.locator('.analysis-error button')).toBeVisible();
  });

  test('should work with non-default provider (fallback logic)', async ({ page }) => {
    // Provider is explicitly NOT default — tests the _resolve_provider fallback
    await setupExecutionMocks(page, {
      providers: [{ ...mockProvider, is_default: false }],
    });

    let analyzeRequestBody: any = null;
    await page.route('**/api/v1/ai/analyze', async (route) => {
      analyzeRequestBody = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAnalyzeJobPending),
      });
    });

    await page.route('**/api/v1/ai/status/99', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAnalyzeJobCompleted),
      });
    });

    await loginAndGoToDashboard(page);
    await page.goto('/runs');
    await page.waitForLoadState('networkidle');

    await page.locator('.data-table tbody tr').first().click();
    await expect(page.locator('.kpi-row')).toBeVisible({ timeout: 5_000 });

    const analyzeBtn = page.locator('.analysis-initial button');
    await analyzeBtn.scrollIntoViewIfNeeded();
    await analyzeBtn.click();

    // Wait for the API call to be made
    await expect(page.locator('.analysis-loading')).toBeVisible();

    // The analyze request should have been sent (provider_id not sent = backend resolves via fallback)
    expect(analyzeRequestBody).toBeTruthy();
    expect(analyzeRequestBody.report_id).toBe(100);

    // Wait for completed result
    await expect(page.locator('.analysis-result')).toBeVisible({ timeout: 10_000 });
  });
});
