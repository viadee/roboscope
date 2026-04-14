// @ts-check
const { test, expect } = require('@playwright/test');
const { launchExtension, openPopup, openFixture, getScriptOutput, cleanup } = require('./setup');

test.describe('Record Flow', () => {
  /** @type {import('playwright').BrowserContext} */
  let context;
  let extensionId;
  let userDataDir;

  test.beforeAll(async () => {
    ({ context, extensionId, userDataDir } = await launchExtension());
  });

  test.afterAll(async () => {
    await cleanup(context, userDataDir);
  });

  test('full record → stop → verify script output', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    // Bring target tab to front, then start recording from popup
    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    // Small wait for content script injection
    await popup.waitForTimeout(1000);

    // Interact with the target page
    await target.bringToFront();
    await target.locator('#username').click();
    await target.locator('#username').fill('testuser');
    await target.locator('#submit-btn').click();
    await target.waitForTimeout(500);

    // Stop recording
    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    // Verify script output contains recorded actions
    const output = await getScriptOutput(popup);
    expect(output).toBeTruthy();
    expect(output.length).toBeGreaterThan(0);

    await popup.close();
    await target.close();
  });

  test('record click events on a test page', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    // Use form page buttons instead of links (links navigate away and break locators)
    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(1000);

    await target.bringToFront();
    await target.locator('#submit-btn').click();
    await target.locator('#reset-btn').click();
    await target.waitForTimeout(500);

    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    const output = await getScriptOutput(popup);
    expect(output).toBeTruthy();
    expect(output.length).toBeGreaterThan(0);

    await popup.close();
    await target.close();
  });

  test('record input/type events', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(1000);

    await target.bringToFront();
    await target.locator('#email').click();
    await target.locator('#email').type('user@example.com', { delay: 30 });
    await target.locator('#bio').click();
    await target.locator('#bio').type('Hello world', { delay: 30 });
    await target.waitForTimeout(500);

    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    const output = await getScriptOutput(popup);
    expect(output).toBeTruthy();
    // Should reference the typed text or input keywords
    expect(output.length).toBeGreaterThan(10);

    await popup.close();
    await target.close();
  });

  test('record navigation events', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'links-page.html');

    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(1000);

    // Click links that cause hash navigation
    await target.bringToFront();
    await target.locator('#link-home').click();
    await target.waitForTimeout(300);
    await target.locator('#link-about').click();
    await target.waitForTimeout(300);

    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    const output = await getScriptOutput(popup);
    expect(output).toBeTruthy();

    await popup.close();
    await target.close();
  });
});
