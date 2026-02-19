import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Test History View', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('navigates to test history page', async ({ page }) => {
    await page.goto('/test-history');
    await expect(page.locator('h1')).toContainText('Test');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });
  });

  test('shows search input and test list panel', async ({ page }) => {
    await page.goto('/test-history');
    await expect(page.locator('.search-box input')).toBeVisible();
    await expect(page.locator('.test-list-panel')).toBeVisible();
  });

  test('shows select prompt when no test is selected', async ({ page }) => {
    await page.goto('/test-history');
    // Should show the "select a test" prompt
    await expect(page.locator('.history-detail-panel .text-muted')).toBeVisible();
  });

  test('handles empty test list gracefully', async ({ page }) => {
    // Mock the API to return empty results
    await page.route('**/api/v1/reports/tests/unique*', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    );

    await page.goto('/test-history');
    // Should show "no tests found" message
    await expect(page.locator('.test-list')).toBeVisible();
  });

  test('displays test history when a test is selected via mocked API', async ({ page }) => {
    // Mock unique tests list
    await page.route('**/api/v1/reports/tests/unique*', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { test_name: 'Login Test', suite_name: 'Auth Suite', last_status: 'PASS', run_count: 5 },
          { test_name: 'Search Test', suite_name: 'UI Suite', last_status: 'FAIL', run_count: 3 },
        ]),
      })
    );

    // Mock test history
    await page.route('**/api/v1/reports/tests/history*', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          test_name: 'Login Test',
          suite_name: 'Auth Suite',
          total_runs: 5,
          pass_count: 4,
          fail_count: 1,
          pass_rate: 80.0,
          history: [
            { report_id: 1, date: '2026-02-10T10:00:00', status: 'PASS', duration_seconds: 1.5, error_message: null },
            { report_id: 2, date: '2026-02-11T10:00:00', status: 'PASS', duration_seconds: 1.3, error_message: null },
            { report_id: 3, date: '2026-02-12T10:00:00', status: 'FAIL', duration_seconds: 2.1, error_message: 'Element not found' },
            { report_id: 4, date: '2026-02-13T10:00:00', status: 'PASS', duration_seconds: 1.4, error_message: null },
            { report_id: 5, date: '2026-02-14T10:00:00', status: 'PASS', duration_seconds: 1.2, error_message: null },
          ],
        }),
      })
    );

    await page.goto('/test-history');

    // Wait for test list to appear
    const loginTestItem = page.locator('.test-list-item', { hasText: 'Login Test' });
    await expect(loginTestItem).toBeVisible({ timeout: 5_000 });

    // Click on the test
    await loginTestItem.click();

    // Verify KPI cards appear
    await expect(page.locator('.kpi-value', { hasText: '5' })).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.kpi-value', { hasText: '80' })).toBeVisible();

    // Verify timeline bar is rendered
    await expect(page.locator('.timeline-bar')).toBeVisible();

    // Verify history table has rows
    const historyRows = page.locator('.data-table tbody tr');
    await expect(historyRows).toHaveCount(5);
  });

  test('search filters the test list', async ({ page }) => {
    // First call returns all tests, second (with search) returns filtered
    let callCount = 0;
    await page.route('**/api/v1/reports/tests/unique*', route => {
      callCount++;
      const url = new URL(route.request().url());
      const search = url.searchParams.get('search');

      if (search && search.includes('Login')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { test_name: 'Login Test', suite_name: 'Auth', last_status: 'PASS', run_count: 3 },
          ]),
        });
      }

      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { test_name: 'Login Test', suite_name: 'Auth', last_status: 'PASS', run_count: 3 },
          { test_name: 'Dashboard Test', suite_name: 'UI', last_status: 'FAIL', run_count: 2 },
        ]),
      });
    });

    await page.goto('/test-history');

    // Initially should show both tests
    await expect(page.locator('.test-list-item')).toHaveCount(2, { timeout: 5_000 });

    // Type in search
    await page.locator('.search-box input').fill('Login');

    // After debounce, should show only filtered test
    await expect(page.locator('.test-list-item')).toHaveCount(1, { timeout: 5_000 });
    await expect(page.locator('.test-list-item', { hasText: 'Login Test' })).toBeVisible();
  });

  test('navigates to test history via query params', async ({ page }) => {
    // Mock APIs
    await page.route('**/api/v1/reports/tests/unique*', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { test_name: 'My Test', suite_name: 'Suite A', last_status: 'PASS', run_count: 2 },
        ]),
      })
    );

    await page.route('**/api/v1/reports/tests/history*', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          test_name: 'My Test',
          suite_name: 'Suite A',
          total_runs: 2,
          pass_count: 2,
          fail_count: 0,
          pass_rate: 100.0,
          history: [
            { report_id: 1, date: '2026-02-10T10:00:00', status: 'PASS', duration_seconds: 1.0, error_message: null },
            { report_id: 2, date: '2026-02-11T10:00:00', status: 'PASS', duration_seconds: 1.1, error_message: null },
          ],
        }),
      })
    );

    // Navigate with query params (as if clicking from report detail)
    await page.goto('/test-history?test=My%20Test&suite=Suite%20A');

    // Should auto-select the test and show history
    await expect(page.locator('.kpi-value', { hasText: '100' })).toBeVisible({ timeout: 5_000 });
  });
});
