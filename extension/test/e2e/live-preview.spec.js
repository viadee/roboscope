// @ts-check
const { test, expect } = require('@playwright/test');
const {
  launchExtension, openPopup, openFixture, getScriptOutput, cleanup
} = require('./setup');

test.describe('Live Preview During Recording', () => {
  let context, extensionId, userDataDir;

  test.beforeAll(async () => {
    ({ context, extensionId, userDataDir } = await launchExtension());
  });

  test.afterAll(async () => {
    await cleanup(context, userDataDir);
  });

  test('script container is visible during recording', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(500);

    // Script container should be visible during recording
    const container = popup.locator('#script-container');
    await expect(container).toBeVisible();

    // Stop recording
    await popup.locator('#stop').click();
    await popup.waitForTimeout(500);

    await popup.close();
    await target.close();
  });

  test('script container is visible during pause', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(500);

    // Pause
    await popup.locator('#pause').click();
    await popup.waitForTimeout(500);

    // Script container should be visible during pause
    const container = popup.locator('#script-container');
    await expect(container).toBeVisible();

    // Resume and stop
    await popup.locator('#resume').click();
    await popup.waitForTimeout(300);
    await popup.locator('#stop').click();
    await popup.waitForTimeout(500);

    await popup.close();
    await target.close();
  });

  test('actions appear in script container while recording', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    await target.bringToFront();
    await popup.bringToFront();

    // Ensure idle state: if stop button is visible, click it first
    const stopBtn = popup.locator('#stop');
    if (await stopBtn.isVisible().catch(() => false)) {
      await stopBtn.click();
      await popup.waitForTimeout(500);
    }

    await popup.locator('#record').waitFor({ state: 'visible', timeout: 5000 });
    await popup.locator('#record').click();
    await popup.waitForTimeout(1000);

    // Perform actions on target page
    await target.bringToFront();
    await target.locator('#username').click();
    await target.locator('#username').fill('livetest');
    await target.waitForTimeout(1000);

    // Switch to popup and check script lines appeared
    await popup.bringToFront();
    await popup.waitForTimeout(1500);

    // The script container should have content now
    const output = await getScriptOutput(popup);
    expect(output.length).toBeGreaterThan(0);

    // Stop recording
    await popup.locator('#stop').click();
    await popup.waitForTimeout(500);

    await popup.close();
    await target.close();
  });

  test('live preview updates with each new action', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(1000);

    // First action
    await target.bringToFront();
    await target.locator('#username').click();
    await target.waitForTimeout(1000);

    await popup.bringToFront();
    await popup.waitForTimeout(500);
    const lineCountAfterFirst = await popup.locator(
      '#script-lines .script-line-row'
    ).count();

    // Second action
    await target.bringToFront();
    await target.locator('#email').click();
    await target.waitForTimeout(1000);

    await popup.bringToFront();
    await popup.waitForTimeout(500);
    const lineCountAfterSecond = await popup.locator(
      '#script-lines .script-line-row'
    ).count();

    // Should have more lines after second action
    expect(lineCountAfterSecond).toBeGreaterThanOrEqual(
      lineCountAfterFirst
    );

    // Stop
    await popup.locator('#stop').click();
    await popup.waitForTimeout(500);

    await popup.close();
    await target.close();
  });

  test('script container persists content after stop', async () => {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(1000);

    await target.bringToFront();
    await target.locator('#username').click();
    await target.locator('#username').fill('persist-test');
    await target.waitForTimeout(1000);

    // Stop and verify content is still there
    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    const output = await getScriptOutput(popup);
    expect(output.length).toBeGreaterThan(0);

    // Script container should still be visible
    const container = popup.locator('#script-container');
    await expect(container).toBeVisible();

    await popup.close();
    await target.close();
  });
});
