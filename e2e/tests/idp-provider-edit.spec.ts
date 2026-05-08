import { test, expect, type APIRequestContext } from '@playwright/test';
import { loginViaApi } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const ADMIN_EMAIL = 'admin@roboscope.local';
const ADMIN_PASSWORD = 'admin123';

async function adminApiToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API}/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  });
  const body = await res.json();
  return body.access_token as string;
}

async function cleanAllIdps(request: APIRequestContext, token: string): Promise<void> {
  const listRes = await request.get(`${API}/auth/idp-providers`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!listRes.ok()) return;
  const idps = (await listRes.json()) as Array<{ id: number }>;
  for (const idp of idps) {
    await request.delete(`${API}/auth/idp-providers/${idp.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  }
}

test.describe('IdP Provider Edit View', () => {
  test.beforeEach(async ({ page, request }) => {
    const token = await adminApiToken(request);
    await cleanAllIdps(request, token);
    await loginViaApi(page);
  });

  test('CREATE flow: fill form → dry-run (fails on bogus issuer) → panel renders, Save stays disabled', async ({ page }) => {
    await page.goto('/admin/identity-providers');
    await page.waitForLoadState('networkidle');

    // From empty state, click "+ Neuer Provider"
    await page.getByRole('button', { name: /Neuer Provider/i }).first().click();
    await page.waitForURL(/\/admin\/identity-providers\/new/);

    // Fill form
    await page.fill('#idp-name', 'E2E Test Provider');
    await page.fill('#idp-issuer-url', 'https://unreachable.invalid');
    await page.fill('#idp-client-id', 'e2e-client');
    await page.fill('[data-testid="client-secret-input"]', 'e2e-secret');

    // Save is disabled until dry-run passes
    await expect(page.getByTestId('save-btn')).toBeDisabled();

    // Run dry-run — will fail on unreachable.invalid
    await page.getByTestId('run-dry-run-btn').click();

    // Wait for dry-run to resolve (probe has up to ~8s budget; overall timeout margin)
    await expect(page.getByTestId('dry-run-panel')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('check-row-issuer_reachable')).toBeVisible();

    // URL should have been replaced with /:id (implicit draft created)
    await expect(page).toHaveURL(/\/admin\/identity-providers\/\d+/);

    // Overall verdict is "Failed" → Save still disabled
    await expect(page.getByTestId('save-btn')).toBeDisabled();
  });

  test('Stale state: after a passed dry-run, editing a field re-disables Save', async ({ page, request }) => {
    const token = await adminApiToken(request);

    // Seed an IdP so we can jump straight into edit mode and skip create chicken-and-egg.
    const createRes = await request.post(`${API}/auth/idp-providers`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        name: 'Stale Target',
        provider_type: 'oidc_azure_ad',
        issuer_url: 'https://unreachable.invalid',
        client_id: 'c',
        client_secret: 's',
        scopes: 'openid profile email',
        group_claim_name: 'groups',
      },
    });
    const seeded = await createRes.json();

    await page.goto(`/admin/identity-providers/${seeded.id}`);
    await page.waitForLoadState('networkidle');

    // Pre-filled form
    await expect(page.locator('#idp-name')).toHaveValue('Stale Target');

    // Run dry-run (will fail, but that's fine — the stale semantics are what we test)
    await page.getByTestId('run-dry-run-btn').click();
    await expect(page.getByTestId('dry-run-panel')).toBeVisible({ timeout: 15000 });

    // Wait for the dry-run to FINISH — `lastDryRunAtForm` is set
    // only after the request resolves, and the stale banner is
    // gated on it. The button re-enables when not loading; that's
    // the cleanest "done" signal.
    await expect(page.getByTestId('run-dry-run-btn')).toBeEnabled({ timeout: 30000 });

    // Panel not stale immediately after
    await expect(page.locator('[data-testid="dry-run-stale-banner"]')).toHaveCount(0);

    // Edit a field → stale banner appears
    await page.fill('#idp-name', 'Stale Target (renamed)');
    await expect(page.locator('[data-testid="dry-run-stale-banner"]')).toBeVisible();

    // Save stays disabled in stale state
    await expect(page.getByTestId('save-btn')).toBeDisabled();
  });

  test('Cancel button returns to the list', async ({ page }) => {
    await page.goto('/admin/identity-providers/new');
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Abbrechen' }).click();
    await page.waitForURL(/\/admin\/identity-providers$/);
  });

  test('Handoff section visible in edit mode, hidden in create mode', async ({ page, request }) => {
    const token = await adminApiToken(request);

    // Seed an IdP so we have an edit-mode route
    const createRes = await request.post(`${API}/auth/idp-providers`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        name: 'Handoff Visibility Test',
        provider_type: 'oidc_azure_ad',
        issuer_url: 'https://unreachable.invalid',
        client_id: 'c',
        client_secret: 's',
        scopes: 'openid profile email',
        group_claim_name: 'groups',
      },
    });
    const seeded = await createRes.json();

    // Edit mode: handoff section should be visible
    await page.goto(`/admin/identity-providers/${seeded.id}`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('handoff-section')).toBeVisible();
    await expect(page.getByTestId('handoff-pdf-btn')).toBeVisible();
    await expect(page.getByTestId('handoff-md-btn')).toBeVisible();

    // Create mode: handoff section should NOT be present
    await page.goto('/admin/identity-providers/new');
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('handoff-section')).toHaveCount(0);
  });

  test('Handoff PDF download button triggers a file download', async ({ page, request }) => {
    const token = await adminApiToken(request);

    const createRes = await request.post(`${API}/auth/idp-providers`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        name: 'Handoff Download Test',
        provider_type: 'oidc_azure_ad',
        issuer_url: 'https://unreachable.invalid',
        client_id: 'c',
        client_secret: 's',
        scopes: 'openid profile email',
        group_claim_name: 'groups',
      },
    });
    const seeded = await createRes.json();

    await page.goto(`/admin/identity-providers/${seeded.id}`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('handoff-pdf-btn')).toBeVisible();

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByTestId('handoff-pdf-btn').click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/idp-handoff/);
    expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  });
});
