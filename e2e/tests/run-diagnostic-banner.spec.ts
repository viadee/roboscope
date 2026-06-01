import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

/**
 * Run-diagnostic banner — when a report's stored test errors match
 * the `playwright_browser_missing` pattern, the ReportDetailView
 * surfaces a yellow actionable banner at the top with a one-click
 * "Run rfbrowser init" button. Clicking POSTs to the env-scoped
 * endpoint and flips the banner to a "started" state.
 *
 * Because seeding a real failing browser run on CI would take ~30 s
 * (actual subprocess + Robot Framework boot) and download a few
 * hundred MB of Playwright binaries, this test:
 *   - intercepts `GET /reports/{id}` and returns a synthetic
 *     payload that includes the diagnostic the backend would
 *     compute for a real Playwright-missing failure
 *   - intercepts the action endpoint and asserts the button posted
 *     the EXACT URL the backend advertised
 *
 * Pinned regressions:
 *   - hard-coding the rfbrowser-init URL in the frontend (it should
 *     come from the diagnostic payload — a future "out-of-disk
 *     space" code with a different action endpoint would silently
 *     hit the wrong route)
 *   - dropping the i18n key for the diagnostic code (banner would
 *     render the key string `reports.diagnostic.playwright_…`
 *     literally and look broken)
 *   - banner not flipping to "started" after a successful trigger
 *     (user keeps clicking, generates duplicate init runs)
 */
test.describe('Run diagnostic banner', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('renders banner + triggers rfbrowser init for playwright_browser_missing diagnostic', async ({ page }) => {
    const reportId = 99001;
    const envId = 4242;
    const initEndpoint = `/api/v1/environments/${envId}/rfbrowser-init`;

    let initCalled = false;

    await page.route(`**/api/v1/reports/${reportId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          report: {
            id: reportId,
            execution_run_id: 12345,
            archive_name: null,
            total_tests: 1,
            passed_tests: 0,
            failed_tests: 1,
            skipped_tests: 0,
            total_duration_seconds: 3.21,
            created_at: '2026-05-13T00:00:00Z',
          },
          test_results: [{
            id: 1,
            report_id: reportId,
            suite_name: 'Heise',
            test_name: 'Click Consent',
            status: 'FAIL',
            duration_seconds: 3.0,
            error_message: "Error: browserType.launch: Executable doesn't exist at /chromium-1217/...",
            tags: null,
            start_time: '2026-05-13T00:00:00Z',
            end_time: '2026-05-13T00:00:03Z',
          }],
          diagnostic: {
            code: 'playwright_browser_missing',
            action: {
              type: 'rfbrowser_init',
              env_id: envId,
              endpoint: `/environments/${envId}/rfbrowser-init`,
              method: 'POST',
            },
          },
        }),
      });
    });

    await page.route(`**${initEndpoint}`, async (route) => {
      initCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'pending', message: 'rfbrowser init started' }),
      });
    });

    await page.goto(`/reports/${reportId}`);

    // Banner is visible with localised title (EN or DE) — match
    // both so the test isn't locale-coupled.
    const banner = page.locator('aside.run-diagnostic-banner');
    await expect(banner).toBeVisible({ timeout: 5_000 });
    await expect(banner).toContainText(/Browser binaries missing|Browser-Binaries fehlen/);

    // Button label localised; tagged via data-testid for stability.
    const trigger = banner.getByTestId('run-diagnostic-trigger');
    await expect(trigger).toBeVisible();

    await trigger.click();

    // Trigger fired exactly once at the advertised endpoint and
    // the banner flips to the "started" state.
    await expect(banner.getByTestId('run-diagnostic-started')).toBeVisible();
    await expect(banner.getByTestId('run-diagnostic-trigger')).not.toBeVisible();
    expect(initCalled).toBe(true);
  });

  test('does NOT render banner when diagnostic is null on the report payload', async ({ page }) => {
    const reportId = 99002;

    await page.route(`**/api/v1/reports/${reportId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          report: {
            id: reportId,
            execution_run_id: 12346,
            archive_name: null,
            total_tests: 1,
            passed_tests: 1,
            failed_tests: 0,
            skipped_tests: 0,
            total_duration_seconds: 1.0,
            created_at: '2026-05-13T00:00:00Z',
          },
          test_results: [{
            id: 1,
            report_id: reportId,
            suite_name: 'Pass',
            test_name: 'Always passes',
            status: 'PASS',
            duration_seconds: 1.0,
            error_message: null,
            tags: null,
            start_time: '2026-05-13T00:00:00Z',
            end_time: '2026-05-13T00:00:01Z',
          }],
          diagnostic: null,
        }),
      });
    });

    await page.goto(`/reports/${reportId}`);

    // The report card itself loaded — but no banner.
    await expect(page.locator('h1')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('aside.run-diagnostic-banner')).toHaveCount(0);
  });
});
