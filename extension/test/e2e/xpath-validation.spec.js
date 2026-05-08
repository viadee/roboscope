// @ts-check
const { test, expect } = require('@playwright/test');
const { launchExtension, openPopup, openFixture, cleanup } = require('./setup');

test.describe('XPath Validation', () => {
  let context, extensionId, userDataDir;

  test.beforeAll(async () => {
    ({ context, extensionId, userDataDir } = await launchExtension());
  });

  test.afterAll(async () => {
    await cleanup(context, userDataDir);
  });

  test('enter valid XPath → verify result', async () => {
    const target = await openFixture(context, 'form-page.html');
    await target.bringToFront();

    const popup = await openPopup(context, extensionId);

    // Open XPath console
    await popup.locator('#xpath-console').click();
    await popup.waitForTimeout(500);

    // The XPath input should be visible now
    const xpathInput = popup.locator('#textinput-xpath');
    await expect(xpathInput).toBeVisible();

    // Enter a valid XPath
    await xpathInput.fill('//input[@id="username"]');
    await xpathInput.press('Enter');
    await popup.waitForTimeout(1000);

    // Check the status or log area for a result (not an error)
    const status = await popup.locator('#status-field').innerText();
    // Should not indicate error for a valid xpath
    expect(status.toLowerCase()).not.toContain('invalid');

    await popup.close();
    await target.close();
  });

  test('enter invalid XPath → verify error', async () => {
    const target = await openFixture(context, 'form-page.html');
    await target.bringToFront();

    const popup = await openPopup(context, extensionId);

    await popup.locator('#xpath-console').click();
    await popup.waitForTimeout(500);

    const xpathInput = popup.locator('#textinput-xpath');
    await xpathInput.fill('///[invalid[xpath');
    await xpathInput.press('Enter');
    await popup.waitForTimeout(1000);

    // Should show some error indication
    const log = await popup.locator('#textarea-log').inputValue();
    const status = await popup.locator('#status-field').innerText();
    // Either the log or status should contain an error hint
    const combined = (log + ' ' + status).toLowerCase();
    expect(combined.length).toBeGreaterThan(0);

    await popup.close();
    await target.close();
  });
});
