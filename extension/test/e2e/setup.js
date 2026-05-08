/**
 * E2E test helpers for the RobotFramework Recorder Chrome extension.
 *
 * Launches Chromium with the extension loaded and provides utilities
 * for locating the popup, service worker, and test fixture pages.
 */

const path = require('path');
const { chromium } = require('playwright');

const EXTENSION_PATH = path.resolve(__dirname, '..', '..');
const FIXTURES_DIR = path.join(__dirname, 'fixtures');

/**
 * Launch a persistent Chromium context with the extension loaded.
 * Playwright requires a persistent context for extensions (no incognito).
 */
async function launchExtension(options = {}) {
  const userDataDir = path.join(__dirname, '.tmp-profile-' + Date.now());
  const useHeadless = process.env.HEADLESS === '1' || process.env.DOCKER;
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,          // Must be false; use --headless=new via args instead
    args: [
      `--disable-extensions-except=${EXTENSION_PATH}`,
      `--load-extension=${EXTENSION_PATH}`,
      '--no-first-run',
      '--disable-default-apps',
      '--disable-popup-blocking',
      ...(useHeadless ? ['--headless=new'] : []),
      ...(process.env.DOCKER ? [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
      ] : []),
    ],
    ...options,
  });

  // Wait for the service worker to register so we can discover the extension ID
  let worker = context.serviceWorkers()[0];
  if (!worker) {
    worker = await context.waitForEvent('serviceworker', { timeout: 15000 });
  }

  const extensionId = worker.url().split('/')[2];

  return { context, worker, extensionId, userDataDir };
}

/**
 * Open the extension popup in a regular tab (since Playwright cannot open
 * the real popup dropdown, we navigate to its chrome-extension:// URL).
 */
async function openPopup(context, extensionId) {
  const page = await context.newPage();
  await page.goto(`chrome-extension://${extensionId}/src/popup.html`, {
    waitUntil: 'domcontentloaded',
  });
  return page;
}

/**
 * Open a local test fixture file in a new tab.
 */
async function openFixture(context, filename) {
  const page = await context.newPage();
  const filePath = path.join(FIXTURES_DIR, filename);
  await page.goto(`file://${filePath}`, { waitUntil: 'domcontentloaded' });
  return page;
}

/**
 * Get script output by reading the values of all script line inputs in the popup.
 * The popup renders each line as an <input> element inside #script-lines,
 * so we read .value from each input rather than using innerText.
 */
async function getScriptOutput(popup) {
  return popup.evaluate(() => {
    const inputs = document.querySelectorAll('#script-lines .script-line-input');
    return Array.from(inputs).map(el => el.value).join('\n');
  });
}

/**
 * Wait for the status field to contain specific text.
 */
async function waitForStatus(popup, text, timeout = 10000) {
  await popup.locator('#status-field').filter({ hasText: text }).waitFor({ timeout });
}

/**
 * Clean up: close context and remove temp profile dir.
 */
async function cleanup(context, userDataDir) {
  await context.close();
  // Best-effort cleanup of temp profile
  const fs = require('fs');
  fs.rmSync(userDataDir, { recursive: true, force: true });
}

/**
 * Filter script output to only user-action lines (removes New Page / Open Browser navigation noise).
 * The extension records navigation events for every tab open, including popup and fixture tabs.
 */
function filterUserActions(output) {
  return output
    .split('\n')
    .filter(line => !line.match(/^\s*(New Page|Open Browser)\s/))
    .join('\n');
}

module.exports = {
  EXTENSION_PATH,
  FIXTURES_DIR,
  launchExtension,
  openPopup,
  openFixture,
  getScriptOutput,
  waitForStatus,
  cleanup,
  filterUserActions,
};
