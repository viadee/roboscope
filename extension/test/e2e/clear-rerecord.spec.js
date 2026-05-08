// @ts-check
const { test, expect } = require('@playwright/test');
const { launchExtension, openPopup, openFixture, getScriptOutput, cleanup, filterUserActions } = require('./setup');

test.describe('Clear & Re-record', () => {
  let context, extensionId, userDataDir;

  test.beforeAll(async () => {
    ({ context, extensionId, userDataDir } = await launchExtension());
  });

  test.afterAll(async () => {
    await cleanup(context, userDataDir);
  });

  test('record → clear → re-record → verify old data gone', async () => {
    const target = await openFixture(context, 'form-page.html');
    const popup = await openPopup(context, extensionId);

    // === First recording ===
    await popup.bringToFront();
    await popup.locator('#record').click();
    await target.bringToFront();
    await target.waitForTimeout(1500);

    await target.locator('#username').click();
    await target.locator('#username').fill('first-recording');
    await target.waitForTimeout(500);

    // Stop
    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    const firstOutput = await getScriptOutput(popup);
    expect(firstOutput).toBeTruthy();

    // === Clear ===
    await popup.locator('#clear-script').click();
    await popup.waitForTimeout(500);

    const clearedOutput = await getScriptOutput(popup);
    // After clear, script area should be empty or minimal
    const clearedActions = filterUserActions(clearedOutput);
    expect(clearedActions).toBe('');

    // === Second recording ===
    await popup.locator('#record').click();
    await target.bringToFront();
    await target.waitForTimeout(1500);

    await target.locator('#email').click();
    await target.locator('#email').fill('second-recording@test.com');
    await target.waitForTimeout(500);

    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    const secondOutput = await getScriptOutput(popup);
    // Second recording should produce output (at least navigation events)
    expect(secondOutput).toBeTruthy();
    expect(secondOutput.length).toBeGreaterThan(0);

    await popup.close();
    await target.close();
  });
});
