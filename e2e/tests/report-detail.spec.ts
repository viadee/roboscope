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
