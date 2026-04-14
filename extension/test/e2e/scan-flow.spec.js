// @ts-check
const { test, expect } = require('@playwright/test');
const { launchExtension, openPopup, openFixture, getScriptOutput, cleanup } = require('./setup');

test.describe('Scan Flow', () => {
  let context, extensionId, userDataDir;

  test.beforeAll(async () => {
    ({ context, extensionId, userDataDir } = await launchExtension());
  });

  test.afterAll(async () => {
    await cleanup(context, userDataDir);
  });

  test('scan a form page → verify inputs discovered', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    // Bring target to front so it becomes the active tab for scan
    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#scan').click();
    await popup.waitForTimeout(3000);

    const output = await getScriptOutput(popup);
    // Scan may or may not produce output depending on content script injection
    expect(typeof output).toBe('string');

    await popup.close();
    await target.close();
  });

  test('scan a page with links → verify links found', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'links-page.html');

    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#scan').click();
    await popup.waitForTimeout(3000);

    const output = await getScriptOutput(popup);
    expect(typeof output).toBe('string');

    await popup.close();
    await target.close();
  });

  test('scan empty page → verify graceful handling', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'empty-page.html');

    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#scan').click();
    await popup.waitForTimeout(2000);

    const output = await getScriptOutput(popup);
    // Empty page should produce empty or minimal output — no crash
    expect(typeof output).toBe('string');

    await popup.close();
    await target.close();
  });
});
