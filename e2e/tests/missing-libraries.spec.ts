import { test, expect } from '../fixtures/auth.fixture';

/**
 * Tests for missing library detection on Report detail page.
 * Explorer pre-run check is tested implicitly via the modal component.
 */

/** Close the welcome tour dialog if it appears. */
async function dismissTour(page: import('@playwright/test').Page) {
  const closeBtn = page.locator('dialog button:has-text("×")').first();
  if (await closeBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await closeBtn.click();
    await closeBtn.waitFor({ state: 'hidden', timeout: 2000 }).catch(() => {});
  }
}

test.describe('Report: Missing Libraries Card', () => {
  test('shows missing libraries card with install buttons', async ({ authenticatedPage: page }) => {
    await dismissTour(page);

    // Mock report detail - use regex for exact path (use high ID to avoid collisions)
    await page.route(/\/api\/v1\/reports\/9901$/, (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          report: {
            id: 9901, execution_run_id: 9901, archive_name: null,
            total_tests: 3, passed_tests: 1, failed_tests: 2, skipped_tests: 0,
            total_duration_seconds: 10.5, created_at: '2025-01-01T00:00:00',
          },
          test_results: [
            { id: 1, report_id: 9901, suite_name: 'Suite', test_name: 'Test OK', status: 'PASS',
              duration_seconds: 2.0, error_message: null, tags: null, start_time: null, end_time: null },
            { id: 2, report_id: 9901, suite_name: 'Suite', test_name: 'Test Lib', status: 'FAIL',
              duration_seconds: 1.0, error_message: "Importing library 'SeleniumLibrary' failed", tags: null, start_time: null, end_time: null },
            { id: 3, report_id: 9901, suite_name: 'Suite', test_name: 'Test Req', status: 'FAIL',
              duration_seconds: 1.0, error_message: "No module named 'requests'", tags: null, start_time: null, end_time: null },
          ],
        }),
      });
    });

    // Mock missing-libraries endpoint
    await page.route('**/api/v1/reports/9901/missing-libraries', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          environment_id: 1,
          environment_name: 'Default',
          libraries: [
            { library_name: 'SeleniumLibrary', pypi_package: 'robotframework-seleniumlibrary' },
            { library_name: 'requests', pypi_package: 'robotframework-requests' },
          ],
        }),
      });
    });

    // Mock AI providers (empty)
    await page.route('**/api/v1/ai/providers', (route) => {
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });

    await page.goto('/reports/9901', { waitUntil: 'networkidle' });
    await dismissTour(page);

    // Missing Libraries card should be visible
    const card = page.locator('.missing-libs-card');
    await expect(card).toBeVisible({ timeout: 5000 });

    // Check library names within the card (exact match to avoid substring collision)
    await expect(card.getByText('SeleniumLibrary', { exact: true })).toBeVisible();
    await expect(card.getByText('robotframework-seleniumlibrary')).toBeVisible();
    await expect(card.getByText('robotframework-requests')).toBeVisible();

    // Install All button should be visible (in header, language-agnostic selector)
    await expect(card.locator('.missing-libs-header button')).toBeVisible();
  });

  test('install button calls package install API', async ({ authenticatedPage: page }) => {
    await dismissTour(page);

    await page.route(/\/api\/v1\/reports\/9902$/, (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          report: {
            id: 9902, execution_run_id: 9902, archive_name: null,
            total_tests: 2, passed_tests: 0, failed_tests: 2, skipped_tests: 0,
            total_duration_seconds: 5.0, created_at: '2025-01-01T00:00:00',
          },
          test_results: [
            { id: 1, report_id: 9902, suite_name: 'Suite', test_name: 'Test A', status: 'FAIL',
              duration_seconds: 1.0, error_message: "Importing library 'DataDriver' failed", tags: null, start_time: null, end_time: null },
          ],
        }),
      });
    });

    await page.route('**/api/v1/reports/9902/missing-libraries', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          environment_id: 5,
          environment_name: 'TestEnv',
          libraries: [
            { library_name: 'DataDriver', pypi_package: 'robotframework-datadriver' },
          ],
        }),
      });
    });

    await page.route('**/api/v1/ai/providers', (route) => {
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });

    // Intercept install API call
    let installCalled = false;
    await page.route('**/api/v1/environments/5/packages', (route) => {
      if (route.request().method() === 'POST') {
        installCalled = true;
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 99, environment_id: 5, package_name: 'robotframework-datadriver',
            version: null, installed_version: '1.11.0', install_status: 'installed', install_error: null,
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.goto('/reports/9902', { waitUntil: 'networkidle' });
    await dismissTour(page);

    const card = page.locator('.missing-libs-card');
    await expect(card).toBeVisible({ timeout: 5000 });

    // Click install for the single library (has-text matches substring, works for DE "Installieren")
    await card.locator('button:has-text("Install")').first().click();

    // Wait for install API call
    await page.waitForTimeout(1000);
    expect(installCalled).toBe(true);
  });

  test('shows no missing libraries card when no libraries missing', async ({ authenticatedPage: page }) => {
    await dismissTour(page);

    await page.route(/\/api\/v1\/reports\/2$/, (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          report: {
            id: 2, execution_run_id: 2, archive_name: null,
            total_tests: 2, passed_tests: 2, failed_tests: 0, skipped_tests: 0,
            total_duration_seconds: 5.0, created_at: '2025-01-01T00:00:00',
          },
          test_results: [
            { id: 1, report_id: 2, suite_name: 'Suite', test_name: 'Test A', status: 'PASS',
              duration_seconds: 2.0, error_message: null, tags: null, start_time: null, end_time: null },
          ],
        }),
      });
    });

    await page.route('**/api/v1/reports/2/missing-libraries', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ environment_id: 1, environment_name: 'Default', libraries: [] }),
      });
    });

    await page.route('**/api/v1/ai/providers', (route) => {
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });

    await page.goto('/reports/2', { waitUntil: 'networkidle' });
    await dismissTour(page);

    // Missing Libraries card should NOT be visible
    await expect(page.locator('.missing-libs-card')).not.toBeVisible({ timeout: 3000 });
  });

  test('shows hint when no environment linked', async ({ authenticatedPage: page }) => {
    await dismissTour(page);

    await page.route(/\/api\/v1\/reports\/3$/, (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          report: {
            id: 3, execution_run_id: 3, archive_name: null,
            total_tests: 1, passed_tests: 0, failed_tests: 1, skipped_tests: 0,
            total_duration_seconds: 1.0, created_at: '2025-01-01T00:00:00',
          },
          test_results: [
            { id: 1, report_id: 3, suite_name: 'Suite', test_name: 'Test A', status: 'FAIL',
              duration_seconds: 1.0, error_message: "Importing library 'Browser' failed", tags: null, start_time: null, end_time: null },
          ],
        }),
      });
    });

    await page.route('**/api/v1/reports/3/missing-libraries', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          environment_id: null,
          environment_name: null,
          libraries: [
            { library_name: 'Browser', pypi_package: 'robotframework-browser' },
          ],
        }),
      });
    });

    await page.route('**/api/v1/ai/providers', (route) => {
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });

    await page.goto('/reports/3', { waitUntil: 'networkidle' });
    await dismissTour(page);

    const card = page.locator('.missing-libs-card');
    await expect(card).toBeVisible({ timeout: 5000 });

    // Should show the hint (no install buttons since no env)
    await expect(card.locator('.missing-libs-hint')).toBeVisible();

    // Install All button should NOT be visible (no env)
    await expect(card.locator('button:has-text("Install All")')).not.toBeVisible();
  });
});
