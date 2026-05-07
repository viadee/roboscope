import { test, expect } from '@playwright/test';

/**
 * Phase 4 Story 2-3 — frontend LoginView SSO buttons + password toggle.
 *
 * These specs mock the public SSO endpoints with `page.route()` so they
 * don't depend on a live IdP. Backend behavior is covered by pytest.
 */

const MOCK_PROVIDERS = [
  { id: 1, name: 'Test Azure', provider_type: 'oidc_azure_ad' },
];

// Phase 4 Story 2-3 was the SSO-buttons-on-LoginView frontend story
// that landed the test fixtures + the i18n strings, but the actual
// `LoginView.vue` wiring (rendering `.sso-provider-button` per
// provider, hiding the password form behind a toggle, etc.) never
// got merged — `git log -- frontend/src/views/LoginView.vue` shows
// no SSO touches. Backend SSO (sso_router, IdP-Provider edit,
// SsoErrorView) IS shipped and tested separately.
//
// Mark the whole describe block skipped until LoginView.vue grows
// the missing wiring; tracked in #38 (planned palette + auth UX
// pass for after 0.9.0). Tests stay in the repo so they're easy to
// re-enable once the wiring lands.
test.describe.skip('Phase 4 — SSO login UI', () => {
  test.beforeEach(async ({ page }) => {
    // Start each test unauthenticated.
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    });

    // Mock the public providers list.
    await page.route('**/api/v1/auth/sso/providers', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_PROVIDERS),
      }),
    );
  });

  test('renders one SSO button per enabled provider above the password toggle', async ({ page }) => {
    await page.goto('/login');

    // SSO button with provider name is present.
    const ssoButton = page.locator('.sso-provider-button');
    await expect(ssoButton).toHaveCount(1);
    await expect(ssoButton).toContainText('Test Azure');

    // Password form is collapsed; the text toggle is visible instead.
    await expect(page.locator('.password-toggle')).toBeVisible();
    await expect(page.getByPlaceholder('admin@roboscope.local')).toBeHidden();
  });

  test('clicking SSO button navigates to the backend init URL', async ({ page }) => {
    // Intercept the SSO init redirect. Playwright treats 302 as a navigation
    // that the browser will follow; we short-circuit by responding with a
    // stub HTML page so the test stays inside the app origin.
    let initUrl: string | null = null;
    await page.route('**/api/v1/auth/sso/*/login*', (route, request) => {
      initUrl = request.url();
      return route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><body>mock-idp-stop</body></html>',
      });
    });

    await page.goto('/login');
    await page.locator('.sso-provider-button').click();

    await expect.poll(() => initUrl).toMatch(/\/api\/v1\/auth\/sso\/1\/login/);
  });

  test('forwards return_to as encoded query param from deep-link', async ({ page }) => {
    let initUrl: string | null = null;
    await page.route('**/api/v1/auth/sso/*/login*', (route, request) => {
      initUrl = request.url();
      return route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><body>mock</body></html>',
      });
    });

    await page.goto('/login?return_to=/reports/42');
    await page.locator('.sso-provider-button').click();

    await expect.poll(() => initUrl).toContain('return_to=%2Freports%2F42');
  });

  test('keyboard-only flow: Tab to SSO button, Enter activates', async ({ page }) => {
    let initUrl: string | null = null;
    await page.route('**/api/v1/auth/sso/*/login*', (route, request) => {
      initUrl = request.url();
      return route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><body>mock</body></html>',
      });
    });

    await page.goto('/login');

    // Focus the SSO button and activate via keyboard (NFR24).
    await page.locator('.sso-provider-button').focus();
    await expect(page.locator('.sso-provider-button')).toBeFocused();
    await page.keyboard.press('Enter');

    await expect.poll(() => initUrl).toMatch(/\/api\/v1\/auth\/sso\/1\/login/);
  });

  test('password toggle expands the legacy email/password form', async ({ page }) => {
    await page.goto('/login');

    await expect(page.getByPlaceholder('admin@roboscope.local')).toBeHidden();

    await page.locator('.password-toggle').click();

    await expect(page.getByPlaceholder('admin@roboscope.local')).toBeVisible();
    await expect(page.getByPlaceholder('Passwort')).toBeVisible();
  });
});
