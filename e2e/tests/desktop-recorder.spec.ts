/**
 * Story D-5 — Windows Desktop Recorder, real-UI end-to-end.
 *
 * Pins the desktop transport plumbing through the ACTUAL RoboScope UI:
 *  - Capability gating: the "Desktop (Windows)" radio is enabled only when
 *    `desktop_windows_viable` is true, disabled otherwise.
 *  - Launcher → live: picking the desktop transport and clicking Record
 *    stashes the transport and dispatches the desktop capture task —
 *    `/start-browser` is POSTed with `transport: "desktop_windows"` (the bug
 *    fix: without it the backend would dispatch the WEB recorder).
 *  - Live stream: a desktop `RecordedCommand` (RPA.Windows `Click`) streamed
 *    over SSE renders in the step list.
 *  - Stop & Save: the saved `RecordedFlow` carries `transport:
 *    "desktop_windows"` (the bug fix: it was hardcoded to web, which would
 *    have emitted Browser library instead of RPA.Windows).
 *
 * Native Windows desktop input cannot be generated from a browser e2e, so the
 * captured-command stream is served deterministically over the SSE route
 * (same approach as recorder-lifecycle.spec.ts). The REAL capture pipeline
 * (LL hooks → UIA → translate → enqueue → RPA.Windows emit) is covered by the
 * backend integration test `test_desktop_recorder_task.TestDesktopCaptureIntegration`.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const FAKE_SID = 92201;

const fakeRepos = [{ id: 1, name: 'demo-repo', url: 'file:///tmp/demo', default_branch: 'main' }];

const desktopCommand = {
  id: 'd5cmd000001',
  index: 0,
  keyword: 'Click',
  args: {},
  selector_candidates: [
    {
      strategy: 'automation_id',
      value: 'submitButton',
      quality_score: 92,
      verified_unique: false,
      effective_override: null,
    },
  ],
  active_candidate_index: 0,
  frame_url: null,
  frame_chain: [],
};

function commandSse(): string {
  // A single desktop command, no `event: end` so the step list keeps rendering
  // (the live view flips to browser_ready on first command).
  return `event: command\ndata: ${JSON.stringify(desktopCommand)}\n\n`;
}

interface Captured {
  startBrowserBody?: Record<string, unknown>;
  saveBody?: Record<string, unknown>;
}

async function setupDesktopMocks(
  page: Page,
  opts: { desktopViable: boolean; captured?: Captured } = { desktopViable: true },
) {
  const captured = opts.captured ?? {};

  await page.route('**/api/v1/recordings/sessions/capabilities', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        web_playwright_viable: true,
        desktop_windows_viable: opts.desktopViable,
        desktop_macos_viable: false,
      }),
    }),
  );

  await page.route('**/api/v1/repos', (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(fakeRepos),
    });
  });

  await page.route('**/api/v1/recordings/sessions', (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    return route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: FAKE_SID,
        transport: 'desktop_windows',
        status: 'recording',
      }),
    });
  });

  await page.route(`**/api/v1/recordings/sessions/${FAKE_SID}/start-browser`, (route) => {
    captured.startBrowserBody = route.request().postDataJSON();
    return route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({ session_id: FAKE_SID, task_id: 'desktop-task-1' }),
    });
  });

  await page.route(`**/api/v1/recordings/sessions/${FAKE_SID}/commands**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'Cache-Control': 'no-cache' },
      body: commandSse(),
    }),
  );

  // Abort (DELETE) on stop-and-save.
  await page.route(`**/api/v1/recordings/sessions/${FAKE_SID}`, (route) => {
    if (route.request().method() === 'DELETE') {
      return route.fulfill({ status: 204, body: '' });
    }
    return route.continue();
  });

  await page.route('**/api/v1/recordings/save', (route) => {
    captured.saveBody = route.request().postDataJSON();
    return route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        saved_path: 'flows/desktop_recording.robot',
        bytes_written: 256,
      }),
    });
  });

  return captured;
}

test.describe('Desktop Recorder — capability gating', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('desktop radio is enabled when the host is Windows-viable', async ({ page }) => {
    await setupDesktopMocks(page, { desktopViable: true });
    await page.goto('/recordings/new');

    const desktopRadio = page.locator('input[type=radio][value="desktop_windows"]');
    await expect(desktopRadio).toBeEnabled({ timeout: 8_000 });
  });

  test('desktop radio is disabled when the host is not Windows-viable', async ({ page }) => {
    await setupDesktopMocks(page, { desktopViable: false });
    await page.goto('/recordings/new');

    const desktopRadio = page.locator('input[type=radio][value="desktop_windows"]');
    await expect(desktopRadio).toBeDisabled({ timeout: 8_000 });
  });
});

test.describe('Desktop Recorder — launcher → live → stop & save', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('desktop transport is threaded through start-browser AND the saved flow', async ({
    page,
  }) => {
    const captured = await setupDesktopMocks(page, { desktopViable: true });

    // 1) Launcher: pick the desktop transport + start.
    await page.goto('/recordings/new');
    const desktopRadio = page.locator('input[type=radio][value="desktop_windows"]');
    await expect(desktopRadio).toBeEnabled({ timeout: 8_000 });
    await desktopRadio.check();
    await page.getByRole('button', { name: /Record|Aufnahme|Aufnehmen/i }).click();

    // 2) Live view mounts and dispatches the desktop capture task. The bug
    //    fix: transport MUST be in the /start-browser body.
    await expect(page).toHaveURL(new RegExp(`/recordings/live/${FAKE_SID}`), {
      timeout: 8_000,
    });
    await expect.poll(() => captured.startBrowserBody?.transport, { timeout: 8_000 }).toBe(
      'desktop_windows',
    );

    // 3) The streamed desktop command renders in the step list.
    await expect(page.locator('.recording-live__keyword')).toContainText('Click', {
      timeout: 8_000,
    });

    // 4) Stop & Save → the saved flow carries the desktop transport (bug fix:
    //    was hardcoded to web_playwright → would emit Browser, not RPA.Windows).
    await page.locator('.recording-live__cta').click();
    await expect
      .poll(() => (captured.saveBody?.flow as { transport?: string } | undefined)?.transport, {
        timeout: 8_000,
      })
      .toBe('desktop_windows');

    const savedFlow = captured.saveBody?.flow as {
      transport: string;
      commands: Array<{ keyword: string }>;
    };
    expect(savedFlow.commands.map((c) => c.keyword)).toContain('Click');
  });
});
