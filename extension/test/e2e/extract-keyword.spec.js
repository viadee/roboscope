// @ts-check
const { test, expect } = require('@playwright/test');
const {
  launchExtension, openPopup, openFixture, cleanup
} = require('./setup');

test.describe('Extract Keyword & Resource Export', () => {
  let context, extensionId, userDataDir;

  test.beforeAll(async () => {
    ({ context, extensionId, userDataDir } = await launchExtension());
  });

  test.afterAll(async () => {
    await cleanup(context, userDataDir);
  });

  /**
   * Helper: record a few actions to get script content.
   */
  async function recordAndStop() {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(1000);

    await target.bringToFront();
    await target.locator('#username').click();
    await target.locator('#username').fill('testuser');
    await target.locator('#email').click();
    await target.locator('#email').fill('test@example.com');
    await target.waitForTimeout(500);

    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    return { popup, target };
  }

  async function openActionsView(popup) {
    const [actionsPage] = await Promise.all([
      context.waitForEvent('page'),
      popup.locator('#open-actions-view').click(),
    ]);
    await actionsPage.waitForLoadState('domcontentloaded');
    await actionsPage.waitForTimeout(1500);
    return actionsPage;
  }

  test('extract keyword button exists in actions view', async () => {
    const { popup, target } = await recordAndStop();
    const actionsPage = await openActionsView(popup);

    const extractBtn = actionsPage.locator('#extract-keyword');
    await expect(extractBtn).toBeVisible();

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('export resource button exists in actions view', async () => {
    const { popup, target } = await recordAndStop();
    const actionsPage = await openActionsView(popup);

    const exportResBtn = actionsPage.locator('#export-resource');
    await expect(exportResBtn).toBeVisible();

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('extract keyword stores keyword in storage', async () => {
    const { popup, target } = await recordAndStop();
    const actionsPage = await openActionsView(popup);

    // Auto-answer the prompt dialog
    actionsPage.on('dialog', async dialog => {
      await dialog.accept('Login Flow');
    });

    await actionsPage.locator('#extract-keyword').click();
    await actionsPage.waitForTimeout(1500);

    // Check that keywords were stored
    const keywords = await actionsPage.evaluate(async () => {
      const data = await chrome.storage.local.get({ keywords: [] });
      return data.keywords;
    });
    expect(keywords.length).toBeGreaterThan(0);
    expect(keywords[0].name).toBe('Login Flow');
    expect(keywords[0].lines.length).toBeGreaterThan(0);

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('extract keyword replaces script with call', async () => {
    const { popup, target } = await recordAndStop();
    const actionsPage = await openActionsView(popup);

    actionsPage.on('dialog', async dialog => {
      await dialog.accept('My Keyword');
    });

    await actionsPage.locator('#extract-keyword').click();
    await actionsPage.waitForTimeout(1500);

    // The script should now be a call to the keyword
    const script = await actionsPage.evaluate(async () => {
      const data = await chrome.storage.local.get({ script: '' });
      return data.script;
    });
    expect(script).toContain('My Keyword');

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('control structures stored correctly in storage', async () => {
    const popup = await openPopup(context, extensionId);

    // Store an IF structure
    await popup.evaluate(async () => {
      const lines = [
        '    IF    ${condition}',
        '        Click    //button[@id="ok"]',
        '    ELSE',
        '        Click    //button[@id="cancel"]',
        '    END',
      ];
      await chrome.storage.local.set({
        script: lines.join('\n'),
        canSave: true,
      });
    });

    await popup.waitForTimeout(500);

    // Verify in actions view
    const actionsPage = await openActionsView(popup);

    const rows = actionsPage.locator(
      '#actions-list .script-line-row, #actions-list .action-card'
    );
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    // Get all rendered text
    const bodyText = await actionsPage.locator('#actions-list').innerText();
    expect(bodyText).toContain('IF');

    await actionsPage.close();
    await popup.close();
  });

  test('TRY/EXCEPT structure renders in actions view', async () => {
    const popup = await openPopup(context, extensionId);

    await popup.evaluate(async () => {
      const lines = [
        '    TRY',
        '        Click    //button[@id="submit"]',
        '    EXCEPT    AS    ${error}',
        '        Log    Error: ${error}',
        '    END',
      ];
      await chrome.storage.local.set({
        script: lines.join('\n'),
        canSave: true,
      });
    });

    await popup.waitForTimeout(500);

    const actionsPage = await openActionsView(popup);

    const bodyText = await actionsPage.locator('#actions-list').innerText();
    expect(bodyText).toContain('TRY');
    expect(bodyText).toContain('EXCEPT');

    await actionsPage.close();
    await popup.close();
  });
});
