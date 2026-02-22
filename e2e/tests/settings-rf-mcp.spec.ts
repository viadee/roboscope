import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  const body = await res.json();
  return body.access_token;
}

/** Click the AI tab on the settings page (DE: "KI & Generierung", EN: "AI & Generation") */
async function clickAiTab(page: Page) {
  // The tab is the 4th .tab button
  const tabs = page.locator('.tab');
  await tabs.nth(3).click();
  await page.waitForTimeout(500);
}

test.describe('Settings — rf-mcp Server Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  // ─── UI Tests ─────────────────────────────────────────

  test('AI tab shows rf-mcp server management card', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    await clickAiTab(page);

    // rf-mcp card heading should be visible (DE: "rf-mcp Wissensserver", EN: "rf-mcp Knowledge Server")
    await expect(page.getByRole('heading', { name: /rf-mcp/ })).toBeVisible();
  });

  test('rf-mcp shows stopped status badge by default', async ({ page }) => {
    await page.route('**/ai/rf-mcp/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'stopped',
          running: false,
          port: null,
          pid: null,
          url: '',
          environment_id: null,
          environment_name: null,
          error_message: '',
          installed_version: null,
        }),
      });
    });

    await page.goto('/settings');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    await clickAiTab(page);

    // Should show "Gestoppt" (DE) or "Stopped" (EN) badge
    await expect(page.getByText(/Gestoppt|Stopped/)).toBeVisible();
  });

  test('rf-mcp shows environment selector and install button when stopped', async ({ page }) => {
    await page.route('**/ai/rf-mcp/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'stopped',
          running: false,
          port: null,
          pid: null,
          url: '',
          environment_id: null,
          environment_name: null,
          error_message: '',
          installed_version: null,
        }),
      });
    });

    await page.goto('/settings');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    await clickAiTab(page);

    // Environment selector should be visible
    await expect(page.locator('.rf-mcp-setup select')).toBeVisible();

    // Install & Start button (DE: "Installieren & Starten", EN: "Install & Start")
    await expect(page.getByRole('button', { name: /Installieren|Install/ })).toBeVisible();
  });

  test('rf-mcp shows spinner during installation', async ({ page }) => {
    await page.route('**/ai/rf-mcp/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'installing',
          running: false,
          port: null,
          pid: null,
          url: '',
          environment_id: 1,
          environment_name: 'Test Env',
          error_message: '',
          installed_version: null,
        }),
      });
    });

    await page.goto('/settings');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    await clickAiTab(page);

    // Should show installing spinner and message
    await expect(page.locator('.rf-mcp-progress')).toBeVisible();
    // DE: "robotframework-mcp Paket wird installiert...", EN: "Installing robotframework-mcp..."
    await expect(page.getByText(/robotframework-mcp/)).toBeVisible();
  });

  test('rf-mcp shows running status with server details', async ({ page }) => {
    await page.route('**/ai/rf-mcp/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'running',
          running: true,
          port: 9090,
          pid: 12345,
          url: 'http://localhost:9090/mcp',
          environment_id: 1,
          environment_name: 'Test Environment',
          error_message: '',
          installed_version: '1.2.3',
        }),
      });
    });

    await page.goto('/settings');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    await clickAiTab(page);

    // Should show running badge (DE: "Läuft", EN: "Running")
    await expect(page.getByText(/Läuft|Running/)).toBeVisible();

    // Should show server details
    await expect(page.getByText('http://localhost:9090/mcp')).toBeVisible();
    await expect(page.getByText('Test Environment')).toBeVisible();
    await expect(page.getByText('1.2.3')).toBeVisible();
    await expect(page.getByText('12345')).toBeVisible();

    // Stop button (DE: "Server stoppen", EN: "Stop Server")
    await expect(page.getByRole('button', { name: /stoppen|Stop/ })).toBeVisible();
  });

  test('rf-mcp shows error status with message', async ({ page }) => {
    await page.route('**/ai/rf-mcp/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'error',
          running: false,
          port: null,
          pid: null,
          url: '',
          environment_id: 1,
          environment_name: 'Test Env',
          error_message: 'Server exited immediately: ModuleNotFoundError',
          installed_version: null,
        }),
      });
    });

    await page.goto('/settings');
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });

    await clickAiTab(page);

    // Should show error badge (DE: "Fehler", EN: "Error")
    await expect(page.getByText(/Fehler|Error/).first()).toBeVisible();

    // Should show error message
    await expect(page.getByText(/ModuleNotFoundError/)).toBeVisible();
  });

  // ─── API Tests ─────────────────────────────────────────

  test('API: GET /rf-mcp/status returns status', async ({ page }) => {
    const token = await getAuthToken(page);
    const res = await page.request.get(`${API}/ai/rf-mcp/status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.status).toBeTruthy();
    expect(typeof data.running).toBe('boolean');
  });

  test('API: POST /rf-mcp/setup rejects nonexistent env', async ({ page }) => {
    const token = await getAuthToken(page);
    const res = await page.request.post(`${API}/ai/rf-mcp/setup`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { environment_id: 99999, port: 9090 },
    });
    expect(res.status()).toBe(404);
  });

  test('API: POST /rf-mcp/stop returns stopped status', async ({ page }) => {
    const token = await getAuthToken(page);
    const res = await page.request.post(`${API}/ai/rf-mcp/stop`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.status).toBe('stopped');
  });
});
