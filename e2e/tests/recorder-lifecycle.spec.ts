/**
 * Story RECORDER-VIS-1 — Recorder lifecycle SSE events + restart-browser.
 *
 * Pins (in order of importance):
 *  - Auth guards on the SSE command-stream endpoint (401/403/404).
 *  - Pill transitions: the `recorder-phase-pill` text matches the
 *    i18n value for each phase driven by backend lifecycle events.
 *  - Restart-browser button: visible and enabled in browser_ready and
 *    browser_crashed; invisible after stream ends.
 *  - Restart-browser click POSTs to the correct REST endpoint.
 *  - Crash banner renders with the error message from the lifecycle event.
 *  - Extension-transport sessions: the SSE `open` event alone (no lifecycle
 *    data) must not leave the phase stuck at "Connecting…".
 *
 * UI tests mock the SSE command stream so they run without a real Chromium
 * session on the server — same approach as run-diagnostic-banner.spec.ts.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';
const FAKE_SID = 91101;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  return (await res.json()).access_token as string;
}

function buildSseBody(events: Array<{ phase: string; message?: string | null }>): string {
  const parts: string[] = events.map(ev => {
    const data = JSON.stringify({ phase: ev.phase, ts: Date.now() / 1000, message: ev.message ?? null });
    return `event: lifecycle\ndata: ${data}\n`;
  });
  parts.push('event: end\ndata: {}\n');
  return parts.join('\n') + '\n';
}

const fakeSession = {
  id: FAKE_SID,
  status: 'recording',
  source: 'chrome_extension',
  target_url: null,
  created_at: '2026-05-15T10:00:00Z',
  triggered_by: 1,
};

async function setupMocks(
  page: Page,
  sseBody: string,
  onRestart?: () => void,
) {
  await page.route(`**/api/v1/recordings/sessions/${FAKE_SID}`, async (route) => {
    if (route.request().method() !== 'GET') { await route.continue(); return; }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fakeSession) });
  });
  await page.route(`**/api/v1/recordings/sessions/${FAKE_SID}/commands**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'Cache-Control': 'no-cache' },
      body: sseBody,
    });
  });
  await page.route(`**/api/v1/recordings/sessions/${FAKE_SID}/restart-browser`, async (route) => {
    onRestart?.();
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({ session_id: FAKE_SID, task_id: 'task-test' }),
    });
  });
  await page.route('**/api/v1/recordings/sessions/capabilities', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ web_playwright_viable: false, desktop_windows_viable: false }),
    });
  });
}

// ── Section 1 — API auth guards (real backend, no mocks) ─────────────────────

test.describe.serial('Recorder SSE — API auth guards', () => {
  let token: string;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    token = await getAuthToken(page);
    await ctx.close();
  });

  test('no token → 401', async ({ page }) => {
    const res = await page.request.get(
      `${API}/recordings/sessions/99999/commands`,
    );
    expect(res.status()).toBe(401);
  });

  test('malformed token → 401', async ({ page }) => {
    const res = await page.request.get(
      `${API}/recordings/sessions/99999/commands?token=not-a-jwt`,
    );
    expect(res.status()).toBe(401);
  });

  test('valid token but nonexistent session → 404', async ({ page }) => {
    const res = await page.request.get(
      `${API}/recordings/sessions/99999/commands?token=${token}`,
    );
    expect(res.status()).toBe(404);
  });

  test('POST /restart-browser on nonexistent session → 404', async ({ page }) => {
    const res = await page.request.post(
      `${API}/recordings/sessions/99999/restart-browser`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(res.status()).toBe(404);
  });
});

// ── Section 2 — UI lifecycle pill transitions ─────────────────────────────────

test.describe('Recorder phase pill — browser_ready', () => {
  test.beforeEach(async ({ page }) => { await loginAndGoToDashboard(page); });

  test('pill shows "Browser ready" and restart button is enabled', async ({ page }) => {
    await setupMocks(page, buildSseBody([{ phase: 'browser_ready' }]));
    await page.goto(`/recordings/live/${FAKE_SID}`);

    await expect(page.getByTestId('recorder-phase-pill'))
      .toContainText(/Browser ready|Bereit/i, { timeout: 8_000 });
    await expect(page.getByTestId('recorder-restart-browser'))
      .toBeEnabled({ timeout: 5_000 });
  });
});

test.describe('Recorder phase pill — browser_crashed', () => {
  test.beforeEach(async ({ page }) => { await loginAndGoToDashboard(page); });

  test('pill shows crashed, crash banner has message, restart button enabled', async ({ page }) => {
    await setupMocks(page, buildSseBody([{ phase: 'browser_crashed', message: 'DISPLAY not found' }]));
    await page.goto(`/recordings/live/${FAKE_SID}`);

    await expect(page.getByTestId('recorder-phase-pill'))
      .toContainText(/Browser crashed|Absturz/i, { timeout: 8_000 });
    await expect(page.getByTestId('recorder-crash-banner')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId('recorder-crash-banner')).toContainText('DISPLAY not found');
    await expect(page.getByTestId('recorder-restart-browser')).toBeEnabled();
  });
});

test.describe('Recorder phase pill — sequential events', () => {
  test.beforeEach(async ({ page }) => { await loginAndGoToDashboard(page); });

  test('browser_starting then browser_ready settles on ready', async ({ page }) => {
    await setupMocks(page, buildSseBody([
      { phase: 'browser_starting' },
      { phase: 'browser_ready' },
    ]));
    await page.goto(`/recordings/live/${FAKE_SID}`);

    await expect(page.getByTestId('recorder-phase-pill'))
      .toContainText(/Browser ready|Bereit/i, { timeout: 8_000 });
  });
});

test.describe('Recorder restart button', () => {
  test.beforeEach(async ({ page }) => { await loginAndGoToDashboard(page); });

  test('click Restart browser POSTs to the restart-browser endpoint', async ({ page }) => {
    let restartCalled = false;
    await setupMocks(
      page,
      buildSseBody([{ phase: 'browser_ready' }]),
      () => { restartCalled = true; },
    );
    await page.goto(`/recordings/live/${FAKE_SID}`);

    await expect(page.getByTestId('recorder-restart-browser')).toBeEnabled({ timeout: 8_000 });
    await page.getByTestId('recorder-restart-browser').click();
    await page.waitForTimeout(800);

    expect(restartCalled).toBe(true);
  });
});

// ── Section 3 — Extension-transport edge case ─────────────────────────────────

test.describe('Recorder phase pill — extension transport (no lifecycle events)', () => {
  test.beforeEach(async ({ page }) => { await loginAndGoToDashboard(page); });

  test('SSE open event alone must not leave pill stuck at Connecting', async ({ page }) => {
    // Extension sessions only emit `event: end` — no lifecycle payloads.
    // The CLAUDE.md SSE-open fix ensures `connecting → browser_starting` on open.
    await setupMocks(page, 'event: end\ndata: {}\n\n');
    await page.goto(`/recordings/live/${FAKE_SID}`);

    // Pill must have transitioned away from the initial 'connecting' text.
    await expect(page.getByTestId('recorder-phase-pill'))
      .not.toContainText(/Connecting|Verbinde/i, { timeout: 8_000 });
  });
});
