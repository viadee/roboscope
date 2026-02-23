import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

/**
 * Mock data for report detail API responses.
 */
const mockReport = {
  report: {
    id: 1,
    execution_run_id: 1,
    total_tests: 5,
    passed_tests: 3,
    failed_tests: 2,
    skipped_tests: 0,
    total_duration_seconds: 12.5,
    created_at: '2026-01-15T10:00:00',
  },
  test_results: [
    { id: 1, report_id: 1, suite_name: 'Login Suite', test_name: 'Valid Login', status: 'PASS', duration_seconds: 2.1, error_message: null, tags: 'smoke', start_time: null, end_time: null },
    { id: 2, report_id: 1, suite_name: 'Login Suite', test_name: 'Invalid Login', status: 'PASS', duration_seconds: 1.8, error_message: null, tags: null, start_time: null, end_time: null },
    { id: 3, report_id: 1, suite_name: 'Login Suite', test_name: 'Empty Password', status: 'PASS', duration_seconds: 1.5, error_message: null, tags: null, start_time: null, end_time: null },
    { id: 4, report_id: 1, suite_name: 'Checkout Suite', test_name: 'Add to Cart', status: 'FAIL', duration_seconds: 3.2, error_message: 'Element not found', tags: 'regression', start_time: null, end_time: null },
    { id: 5, report_id: 1, suite_name: 'Checkout Suite', test_name: 'Payment Flow', status: 'FAIL', duration_seconds: 3.9, error_message: 'Timeout waiting for payment', tags: null, start_time: null, end_time: null },
  ],
};

const mockXmlData = {
  suites: [
    {
      name: 'Root Suite',
      source: '/tests',
      status: 'FAIL',
      start_time: '20260115 10:00:00.000',
      end_time: '20260115 10:00:12.500',
      duration: 12.5,
      doc: 'Root test suite',
      suites: [
        {
          name: 'Login Suite',
          source: '/tests/login.robot',
          status: 'PASS',
          start_time: '20260115 10:00:00.000',
          end_time: '20260115 10:00:05.400',
          duration: 5.4,
          doc: '',
          suites: [],
          tests: [
            {
              name: 'Valid Login',
              status: 'PASS',
              start_time: '20260115 10:00:00.000',
              end_time: '20260115 10:00:02.100',
              duration: 2.1,
              doc: '',
              tags: ['smoke'],
              error_message: '',
              keywords: [
                {
                  name: 'Open Browser',
                  type: 'kw',
                  library: 'SeleniumLibrary',
                  status: 'PASS',
                  start_time: '',
                  end_time: '',
                  duration: 0.5,
                  doc: '',
                  arguments: ['http://localhost', 'chrome'],
                  messages: [
                    { timestamp: '20260115 10:00:00.100', level: 'INFO', text: 'Opening browser' },
                  ],
                  keywords: [],
                },
              ],
            },
          ],
        },
      ],
      tests: [],
    },
  ],
  statistics: {
    total: { 'All Tests': { pass: 3, fail: 2, skip: 0 } },
  },
  generated: '20260115 10:00:12.500',
};

test.describe('Report Detail Page', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the report detail API
    await page.route('**/api/v1/reports/1', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockReport),
        });
      }
    });

    // Mock XML data API
    await page.route('**/api/v1/reports/1/xml-data', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockXmlData),
      });
    });

    // Mock HTML report endpoint
    await page.route('**/api/v1/reports/1/html*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><head></head><body><h1>Robot Framework Report</h1></body></html>',
      });
    });

    // Mock ZIP endpoint
    await page.route('**/api/v1/reports/1/zip*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/zip',
        body: Buffer.from('PK mock zip content'),
        headers: {
          'Content-Disposition': 'attachment; filename="report_1.zip"',
        },
      });
    });

    // Mock AI providers (needed by ReportDetailView)
    await page.route('**/api/v1/ai/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await loginAndGoToDashboard(page);
  });

  test('should show 3 tabs: Summary, Detailed Report, HTML Report', async ({ page }) => {
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Check all 3 tabs are visible
    await expect(page.locator('.tab-btn').nth(0)).toBeVisible();
    await expect(page.locator('.tab-btn').nth(1)).toBeVisible();
    await expect(page.locator('.tab-btn').nth(2)).toBeVisible();

    // Summary tab should be active by default
    await expect(page.locator('.tab-btn.active')).toHaveCount(1);
  });

  test('should show KPI cards and test tables in Summary tab', async ({ page }) => {
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // KPI cards
    await expect(page.locator('.kpi-card')).toHaveCount(4);

    // Test count values
    await expect(page.locator('.kpi-value').first()).toContainText('5');

    // Failed tests table
    await expect(page.locator('.data-table')).toHaveCount(2);
  });

  test('should switch to HTML Report tab and show iframe', async ({ page }) => {
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Click HTML Report tab (now 3rd tab)
    await page.locator('.tab-btn').nth(2).click();

    // iframe should be visible
    await expect(page.locator('.html-report-iframe')).toBeVisible();
  });

  test('should switch to Detailed Report tab and show tree', async ({ page }) => {
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Click Detailed Report tab (now 2nd tab)
    await page.locator('.tab-btn').nth(1).click();

    // Wait for XML data to load
    await expect(page.locator('.xml-tree')).toBeVisible({ timeout: 10_000 });

    // Root suite should be visible
    await expect(page.locator('.suite-header').first()).toBeVisible();
    await expect(page.locator('.tree-label').first()).toContainText('Root Suite');
  });

  test('should expand and collapse nodes in Detailed Report', async ({ page }) => {
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Click Detailed Report tab (now 2nd tab)
    await page.locator('.tab-btn').nth(1).click();
    await expect(page.locator('.xml-tree')).toBeVisible({ timeout: 10_000 });

    const xmlTree = page.locator('.xml-tree');

    // Root Suite should be auto-expanded (showing doc text)
    await expect(xmlTree.locator('.tree-doc')).toContainText('Root test suite');

    // Click Root Suite to collapse it
    await xmlTree.locator('.suite-header').first().click();

    // Doc text should now be hidden (collapsed)
    await expect(xmlTree.locator('.tree-doc')).not.toBeVisible({ timeout: 3_000 });

    // Click again to re-expand
    await xmlTree.locator('.suite-header').first().click();
    await expect(xmlTree.locator('.tree-doc')).toBeVisible({ timeout: 3_000 });
  });

  test('should have Download ZIP button', async ({ page }) => {
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // ZIP download button should be visible
    const zipBtn = page.locator('.zip-btn');
    await expect(zipBtn).toBeVisible();
  });

  test('should navigate between tabs without losing state', async ({ page }) => {
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Go to Detailed Report
    await page.locator('.tab-btn').nth(1).click();
    await expect(page.locator('.xml-tree')).toBeVisible({ timeout: 10_000 });

    // Go back to Summary
    await page.locator('.tab-btn').nth(0).click();
    await expect(page.locator('.kpi-card').first()).toBeVisible();

    // Go to HTML Report
    await page.locator('.tab-btn').nth(2).click();
    await expect(page.locator('.html-report-iframe')).toBeVisible();
  });
});

/**
 * AI Failure Analysis tests on the Report Detail page.
 */

const mockProvider = {
  id: 1,
  name: 'Test Provider',
  provider_type: 'openai',
  api_base_url: null,
  has_api_key: true,
  model_name: 'gpt-4o',
  temperature: 0.3,
  max_tokens: 4096,
  is_default: true,
  created_by: 1,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
};

const mockAnalyzeJobPending = {
  id: 99,
  job_type: 'analyze',
  status: 'pending',
  repository_id: 0,
  provider_id: 1,
  report_id: 1,
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
  result_preview: '## Root Cause Analysis\n\n### 1. Add to Cart\n- **Priority**: HIGH\n- Element not found — likely a selector issue.\n\n### 2. Payment Flow\n- **Priority**: CRITICAL\n- Timeout waiting for payment — service may be down.',
  token_usage: 1250,
  started_at: '2026-01-15T10:01:01',
  completed_at: '2026-01-15T10:01:15',
};

const mockAnalyzeJobFailed = {
  ...mockAnalyzeJobPending,
  status: 'failed',
  error_message: 'LLM API returned 429: rate limited',
  started_at: '2026-01-15T10:01:01',
  completed_at: '2026-01-15T10:01:02',
};

/** Report with no failures — analysis card should not appear. */
const mockReportAllPassed = {
  report: {
    id: 2,
    execution_run_id: 2,
    total_tests: 3,
    passed_tests: 3,
    failed_tests: 0,
    skipped_tests: 0,
    total_duration_seconds: 5.4,
    created_at: '2026-01-15T10:00:00',
  },
  test_results: [
    { id: 10, report_id: 2, suite_name: 'Login Suite', test_name: 'Valid Login', status: 'PASS', duration_seconds: 2.1, error_message: null, tags: null, start_time: null, end_time: null },
    { id: 11, report_id: 2, suite_name: 'Login Suite', test_name: 'Invalid Login', status: 'PASS', duration_seconds: 1.8, error_message: null, tags: null, start_time: null, end_time: null },
    { id: 12, report_id: 2, suite_name: 'Login Suite', test_name: 'Empty Password', status: 'PASS', duration_seconds: 1.5, error_message: null, tags: null, start_time: null, end_time: null },
  ],
};

function setupReportMocks(page: import('@playwright/test').Page) {
  return Promise.all([
    page.route('**/api/v1/reports/1', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockReport),
        });
      }
    }),
    page.route('**/api/v1/reports/1/xml-data', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(mockXmlData) });
    }),
    page.route('**/api/v1/reports/1/html*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body></body></html>' });
    }),
    page.route('**/api/v1/reports/1/zip*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/zip', body: Buffer.from('PK') });
    }),
  ]);
}

test.describe('AI Failure Analysis', () => {
  test('should show analysis card with Analyze button when provider is configured', async ({ page }) => {
    await setupReportMocks(page);
    await page.route('**/api/v1/ai/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([mockProvider]),
      });
    });

    await loginAndGoToDashboard(page);
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Analysis card should be visible (report has failures) — scroll into view
    const analysisCard = page.locator('.analysis-card');
    await analysisCard.scrollIntoViewIfNeeded();
    await expect(analysisCard).toBeVisible();
    await expect(analysisCard.locator('h3')).toBeVisible();

    // Analyze button should be visible
    const analyzeBtn = page.locator('.analysis-initial button');
    await expect(analyzeBtn).toBeVisible();
  });

  test('should show no-provider hint when no AI provider is configured', async ({ page }) => {
    await setupReportMocks(page);
    await page.route('**/api/v1/ai/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await loginAndGoToDashboard(page);
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Analysis card should show no-provider hint
    await expect(page.locator('.analysis-card')).toBeVisible();
    await expect(page.locator('.analysis-hint')).toBeVisible();
  });

  test('should not show analysis card when report has no failures', async ({ page }) => {
    await page.route('**/api/v1/reports/2', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockReportAllPassed),
        });
      }
    });
    await page.route('**/api/v1/reports/2/xml-data', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(mockXmlData) });
    });
    await page.route('**/api/v1/reports/2/html*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body></body></html>' });
    });
    await page.route('**/api/v1/ai/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([mockProvider]),
      });
    });

    await loginAndGoToDashboard(page);
    await page.goto('/reports/2');
    await page.waitForLoadState('networkidle');

    // Analysis card should NOT be visible (no failures)
    await expect(page.locator('.analysis-card')).not.toBeVisible();
  });

  test('should show loading state and then completed analysis result', async ({ page }) => {
    await setupReportMocks(page);
    await page.route('**/api/v1/ai/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([mockProvider]),
      });
    });

    // POST /ai/analyze returns pending job
    await page.route('**/api/v1/ai/analyze', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAnalyzeJobPending),
      });
    });

    // First poll returns running, second returns completed
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
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Scroll to analysis card and click Analyze button
    const analyzeBtn = page.locator('.analysis-initial button');
    await analyzeBtn.scrollIntoViewIfNeeded();
    await analyzeBtn.click();

    // Loading state should appear
    await expect(page.locator('.analysis-loading')).toBeVisible();

    // Wait for completed result
    await expect(page.locator('.analysis-result')).toBeVisible({ timeout: 10_000 });

    // Check analysis content is rendered (markdown content is language-independent)
    await expect(page.locator('.analysis-content')).toContainText('Root Cause Analysis');
    await expect(page.locator('.analysis-content')).toContainText('Add to Cart');
    await expect(page.locator('.analysis-content')).toContainText('Payment Flow');

    // Token count shown (check number, not translated label)
    await expect(page.locator('.analysis-footer')).toContainText('1250');

    // Re-analyze button visible
    await expect(page.locator('.analysis-footer button')).toBeVisible();
  });

  test('should show error state when analysis fails', async ({ page }) => {
    await setupReportMocks(page);
    await page.route('**/api/v1/ai/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([mockProvider]),
      });
    });

    await page.route('**/api/v1/ai/analyze', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAnalyzeJobPending),
      });
    });

    // Poll returns failed job
    await page.route('**/api/v1/ai/status/99', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAnalyzeJobFailed),
      });
    });

    await loginAndGoToDashboard(page);
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Scroll to and click Analyze button
    const analyzeBtn = page.locator('.analysis-initial button');
    await analyzeBtn.scrollIntoViewIfNeeded();
    await analyzeBtn.click();

    // Wait for error state
    await expect(page.locator('.analysis-error')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.analysis-error')).toContainText('rate limited');

    // Retry button should be visible
    await expect(page.locator('.analysis-error button')).toBeVisible();
  });

  test('should show error state when API request itself fails', async ({ page }) => {
    await setupReportMocks(page);
    await page.route('**/api/v1/ai/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([mockProvider]),
      });
    });

    // POST /ai/analyze returns 400 error
    await page.route('**/api/v1/ai/analyze', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'No LLM provider configured' }),
      });
    });

    await loginAndGoToDashboard(page);
    await page.goto('/reports/1');
    await page.waitForLoadState('networkidle');

    // Scroll to and click Analyze button
    const analyzeBtn = page.locator('.analysis-initial button');
    await analyzeBtn.scrollIntoViewIfNeeded();
    await analyzeBtn.click();

    // Error state should show the API error
    await expect(page.locator('.analysis-error')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.analysis-error')).toContainText('No LLM provider configured');
  });
});
