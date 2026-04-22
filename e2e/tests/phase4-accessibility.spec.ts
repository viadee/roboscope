import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/**
 * Phase 4 Story 4-8 — axe-core Playwright accessibility gate.
 *
 * Asserts that the Phase-4 views render without WCAG 2.1 AA violations.
 * Scope-limited to views introduced or meaningfully changed in Phase 4:
 *   - LoginView (post Story 2-3 SSO buttons)
 *   - SsoErrorView (Story 2-7)
 *   - FirstLoginView (Stories 4-2 + 4-5)
 *
 * Deeper views (TeamListView / TeamDetailView) are gated by the same
 * patterns; the smoke here is the CI gate.
 */

async function seedAuthed(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.setItem('access_token', 'test-token');
    localStorage.setItem('refresh_token', 'test-token');
  });
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        email: 'alice@test.com',
        username: 'alice',
        role: 'editor',
        is_active: true,
        created_at: new Date().toISOString(),
        last_login_at: null,
        teams: [],
        default_team_id: null,
        effective_roles_by_repo: {},
        first_login_complete: false,
      }),
    }),
  );
}

test.describe('Phase 4 accessibility (axe-core)', () => {
  test('LoginView has no critical / serious violations', async ({ page }) => {
    await page.route('**/api/v1/auth/sso/providers', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
    );
    await page.route('**/api/v1/auth/sso/public-settings', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ hide_local_login_form: false, admin_contact_email: '' }),
      }),
    );
    await page.goto('/login');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );
    expect(blocking, JSON.stringify(blocking, null, 2)).toHaveLength(0);
  });

  test('SsoErrorView has no critical / serious violations', async ({ page }) => {
    await page.route('**/api/v1/auth/sso/public-settings', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          hide_local_login_form: false,
          admin_contact_email: 'admin@example.com',
        }),
      }),
    );
    await page.goto('/sso-error?code=idp.unreachable');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );
    expect(blocking, JSON.stringify(blocking, null, 2)).toHaveLength(0);
  });

  test('FirstLoginView has no critical / serious violations', async ({ page }) => {
    await seedAuthed(page);
    await page.goto('/welcome');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );
    expect(blocking, JSON.stringify(blocking, null, 2)).toHaveLength(0);
  });
});
