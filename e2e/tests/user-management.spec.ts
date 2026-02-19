import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@mateox.local';
const PASSWORD = 'admin123';

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  const body = await res.json();
  return body.access_token;
}

async function goToUsersTab(page: Page) {
  await page.goto('/settings');
  await expect(page.locator('h1', { hasText: 'Einstellungen' })).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: 'Benutzer' }).click();
  await expect(page.locator('h3', { hasText: 'Benutzerverwaltung' })).toBeVisible({ timeout: 5_000 });
}

async function deleteUserViaApi(page: Page, token: string, userId: number) {
  await page.request.delete(`${API}/auth/users/${userId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

test.describe('User Management — E2E', () => {
  let token: string;

  test.beforeEach(async ({ page }) => {
    token = await getAuthToken(page);
    await loginAndGoToDashboard(page);
  });

  // ─── API-Level Tests ─────────────────────────────────────────────

  test('GET /auth/users should return user list', async ({ page }) => {
    const res = await page.request.get(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThan(0);
    // Admin user should exist
    const admin = body.find((u: any) => u.email === EMAIL);
    expect(admin).toBeTruthy();
    expect(admin.role).toBe('admin');
  });

  test('POST /auth/users should create a new user', async ({ page }) => {
    const username = `testuser-${Date.now()}`;
    const res = await page.request.post(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        email: `${username}@test.local`,
        username,
        password: 'test123456',
        role: 'runner',
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.username).toBe(username);
    expect(body.role).toBe('runner');
    expect(body.is_active).toBe(true);

    // Cleanup
    await deleteUserViaApi(page, token, body.id);
  });

  test('POST /auth/users should reject duplicate email', async ({ page }) => {
    const username = `dup-${Date.now()}`;
    const email = `${username}@test.local`;

    // Create first user
    const res1 = await page.request.post(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { email, username, password: 'test123456', role: 'viewer' },
    });
    expect(res1.status()).toBe(201);
    const user1 = await res1.json();

    // Try creating a user with same email
    const res2 = await page.request.post(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { email, username: `${username}-2`, password: 'test123456', role: 'viewer' },
    });
    expect(res2.status()).toBe(409);

    // Cleanup
    await deleteUserViaApi(page, token, user1.id);
  });

  test('PATCH /auth/users should update user role', async ({ page }) => {
    const username = `role-${Date.now()}`;
    const createRes = await page.request.post(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { email: `${username}@test.local`, username, password: 'test123456', role: 'viewer' },
    });
    const user = await createRes.json();

    const patchRes = await page.request.patch(`${API}/auth/users/${user.id}`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { role: 'editor' },
    });
    expect(patchRes.ok()).toBeTruthy();
    const updated = await patchRes.json();
    expect(updated.role).toBe('editor');

    // Cleanup
    await deleteUserViaApi(page, token, user.id);
  });

  test('user list endpoint should reject invalid token', async ({ page }) => {
    const res = await page.request.get(`${API}/auth/users`, {
      headers: { Authorization: 'Bearer invalid-token' },
    });
    expect([401, 403]).toContain(res.status());
  });

  // ─── UI-Level Tests ──────────────────────────────────────────────

  test('users tab should show user table with admin user', async ({ page }) => {
    await goToUsersTab(page);

    const table = page.locator('.data-table');
    await expect(table).toBeVisible();

    // Admin user should be in the table
    await expect(table.getByRole('cell', { name: 'admin' }).first()).toBeVisible();
    await expect(table.getByRole('cell', { name: EMAIL })).toBeVisible();
  });

  test('should create a new user via UI', async ({ page }) => {
    const username = `ui-create-${Date.now()}`;

    await goToUsersTab(page);

    // Click "Benutzer hinzufügen"
    await page.getByRole('button', { name: /Benutzer hinzufügen/ }).click();

    // Fill the form
    await expect(page.getByPlaceholder('max.mustermann')).toBeVisible({ timeout: 3_000 });
    await page.getByPlaceholder('max.mustermann').fill(username);
    await page.getByPlaceholder('max@example.com').fill(`${username}@test.local`);
    await page.getByPlaceholder('Mindestens 6 Zeichen').fill('test123456');

    // Submit
    await page.getByRole('button', { name: 'Erstellen', exact: true }).click();

    // Modal should close and user should appear in table
    await expect(page.getByPlaceholder('max.mustermann')).not.toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.data-table').getByRole('cell', { name: username, exact: true })).toBeVisible({ timeout: 5_000 });

    // Cleanup via API
    const usersRes = await page.request.get(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const users = await usersRes.json();
    const created = users.find((u: any) => u.username === username);
    if (created) await deleteUserViaApi(page, token, created.id);
  });

  test('should edit a user via UI', async ({ page }) => {
    const username = `ui-edit-${Date.now()}`;

    // Create user via API
    const createRes = await page.request.post(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { email: `${username}@test.local`, username, password: 'test123456', role: 'viewer' },
    });
    const user = await createRes.json();

    await goToUsersTab(page);

    // Find the user row and click "Bearbeiten"
    const row = page.locator('tr', { hasText: username });
    await expect(row).toBeVisible({ timeout: 5_000 });
    await row.getByRole('button', { name: 'Bearbeiten' }).click();

    // Edit dialog should open
    await expect(page.locator('.modal-header', { hasText: 'Benutzer bearbeiten' })).toBeVisible({ timeout: 3_000 });

    // Change role to editor
    await page.locator('.modal select').selectOption('editor');
    await page.getByRole('button', { name: 'Speichern', exact: true }).click();

    // Dialog should close, role should be updated
    await expect(page.locator('.modal-header', { hasText: 'Benutzer bearbeiten' })).not.toBeVisible({ timeout: 5_000 });
    await expect(row.getByText('editor')).toBeVisible({ timeout: 5_000 });

    // Cleanup
    await deleteUserViaApi(page, token, user.id);
  });

  test('should toggle user active status via UI', async ({ page }) => {
    const username = `ui-toggle-${Date.now()}`;

    // Create user via API
    const createRes = await page.request.post(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { email: `${username}@test.local`, username, password: 'test123456', role: 'runner' },
    });
    const user = await createRes.json();

    await goToUsersTab(page);

    const row = page.locator('tr', { hasText: username });
    await expect(row).toBeVisible({ timeout: 5_000 });

    // Should show "Aktiv" initially
    await expect(row.getByText('Aktiv', { exact: true })).toBeVisible();

    // Click "Deaktivieren"
    await row.getByRole('button', { name: 'Deaktivieren' }).click();

    // Should now show "Inaktiv"
    await expect(row.getByText('Inaktiv', { exact: true })).toBeVisible({ timeout: 5_000 });

    // Toast should appear
    await expect(page.locator('.toast', { hasText: /deaktivier/ })).toBeVisible({ timeout: 5_000 });

    // Cleanup
    await deleteUserViaApi(page, token, user.id);
  });

  test('should delete a user via UI', async ({ page }) => {
    const username = `ui-delete-${Date.now()}`;

    // Create user via API
    await page.request.post(`${API}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { email: `${username}@test.local`, username, password: 'test123456', role: 'viewer' },
    });

    await goToUsersTab(page);

    const row = page.locator('tr', { hasText: username });
    await expect(row).toBeVisible({ timeout: 5_000 });

    // Accept the confirm dialog
    page.on('dialog', (dialog) => dialog.accept());

    // Click "Löschen"
    await row.getByRole('button', { name: 'Löschen' }).click();

    // User should disappear from table
    await expect(row).not.toBeVisible({ timeout: 5_000 });

    // Toast should appear
    await expect(page.locator('.toast', { hasText: /gelöscht/ })).toBeVisible({ timeout: 5_000 });
  });
});
