// @ts-check
const { test, expect } = require('@playwright/test');
const { launchExtension, openPopup, openFixture, getScriptOutput, cleanup } = require('./setup');

test.describe('Export & Download', () => {
  let context, extensionId, userDataDir;

  test.beforeAll(async () => {
    ({ context, extensionId, userDataDir } = await launchExtension());
  });

  test.afterAll(async () => {
    await cleanup(context, userDataDir);
  });

  /**
   * Helper: record a quick action on the form page and stop.
   */
  async function recordQuickAction() {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    await popup.bringToFront();
    await popup.locator('#record').click();
    await target.bringToFront();
    await target.waitForTimeout(1500);

    await target.locator('#username').click();
    await target.locator('#username').fill('downloadtest');
    await target.waitForTimeout(500);

    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    return { popup, target };
  }

  test('record actions → verify output exists and save button enabled', async () => {
    const { popup, target } = await recordQuickAction();

    const output = await getScriptOutput(popup);
    expect(output).toBeTruthy();
    expect(output.length).toBeGreaterThan(0);

    // Save button should be enabled after recording
    const saveBtn = popup.locator('#save');
    const isDisabled = await saveBtn.getAttribute('disabled');
    expect(isDisabled).toBeNull();

    // Copy button should also be enabled
    const copyBtn = popup.locator('#copy');
    const copyDisabled = await copyBtn.getAttribute('disabled');
    expect(copyDisabled).toBeNull();

    await popup.close();
    await target.close();
  });

  test('export as Browser library format', async () => {
    // Ensure Browser library is selected
    const settingsPopup = await openPopup(context, extensionId);
    await settingsPopup.locator('#settings').click();
    await settingsPopup.waitForTimeout(300);
    await settingsPopup.locator('#target_rfbrowser').check();
    await settingsPopup.waitForTimeout(500);
    await settingsPopup.close();

    const { popup, target } = await recordQuickAction();
    const output = await getScriptOutput(popup);

    // Popup shows raw recorded event lines (New Page, Fill Text, etc.)
    expect(output).toBeTruthy();
    expect(output.length).toBeGreaterThan(0);

    await popup.close();
    await target.close();
  });

  test('export as SeleniumLibrary format', async () => {
    // Switch to SeleniumLibrary
    const settingsPopup = await openPopup(context, extensionId);
    await settingsPopup.locator('#settings').click();
    await settingsPopup.waitForTimeout(300);
    await settingsPopup.locator('#target_seleniumlibrary').check();
    await settingsPopup.waitForTimeout(500);
    await settingsPopup.close();

    const { popup, target } = await recordQuickAction();
    const output = await getScriptOutput(popup);

    // SeleniumLibrary uses different keywords (Open Browser, Input Text, Click Element)
    expect(output).toBeTruthy();
    expect(output.length).toBeGreaterThan(0);

    await popup.close();
    await target.close();
  });
});
