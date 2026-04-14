// @ts-check
const { test, expect } = require('@playwright/test');
const { launchExtension, openPopup, openFixture, cleanup } = require('./setup');

test.describe('Actions View', () => {
  let context, extensionId, userDataDir;

  test.beforeAll(async () => {
    ({ context, extensionId, userDataDir } = await launchExtension());
  });

  test.afterAll(async () => {
    await cleanup(context, userDataDir);
  });

  /**
   * Record some actions so there's data to view, then stop recording.
   * Returns the popup page (target & popup stay open for the caller).
   */
  async function recordSomeActions() {
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    // Start recording — must bring target to front first so the extension
    // knows which tab to record on, then click Record in the popup.
    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(1000);

    // Perform actions on the target page
    await target.bringToFront();
    await target.locator('#username').click();
    await target.locator('#username').fill('testuser');
    await target.locator('#email').click();
    await target.locator('#email').fill('test@example.com');
    await target.locator('#submit-btn').click();
    await target.waitForTimeout(500);

    // Stop recording
    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(1000);

    return { popup, target };
  }

  /**
   * Open the actions view tab from the popup and wait for it to load.
   */
  async function openActionsView(popup) {
    const [actionsPage] = await Promise.all([
      context.waitForEvent('page'),
      popup.locator('#open-actions-view').click(),
    ]);
    await actionsPage.waitForLoadState('domcontentloaded');
    // Give the JS time to read storage and render
    await actionsPage.waitForTimeout(1500);
    return actionsPage;
  }

  test('actions view loads and shows recorded script lines', async () => {
    const { popup, target } = await recordSomeActions();
    const actionsPage = await openActionsView(popup);

    // The actions-list container should have script-line-row elements
    const rows = actionsPage.locator('#actions-list .script-line-row');
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);

    // Each row should have a line number and a script-line-input with content
    const firstInput = rows.first().locator('.script-line-input');
    const firstValue = await firstInput.inputValue();
    expect(firstValue.trim().length).toBeGreaterThan(0);

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('actions view script lines contain recorded page URL', async () => {
    const { popup, target } = await recordSomeActions();
    const actionsPage = await openActionsView(popup);

    // Collect all line values
    const inputs = actionsPage.locator('#actions-list .script-line-input');
    const count = await inputs.count();
    const lines = [];
    for (let i = 0; i < count; i++) {
      lines.push(await inputs.nth(i).inputValue());
    }
    const allText = lines.join('\n');

    // The first recorded action is always the URL of the page
    expect(allText).toContain('form-page.html');

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('actions view refresh button reloads data', async () => {
    const { popup, target } = await recordSomeActions();
    const actionsPage = await openActionsView(popup);

    // Count rows before refresh
    const rowsBefore = await actionsPage.locator('#actions-list .script-line-row').count();

    // Click refresh
    await actionsPage.locator('#refresh').click();
    await actionsPage.waitForTimeout(1000);

    // Rows should still be there (same data)
    const rowsAfter = await actionsPage.locator('#actions-list .script-line-row').count();
    expect(rowsAfter).toBe(rowsBefore);

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('actions view copy-script button copies to clipboard', async () => {
    const { popup, target } = await recordSomeActions();
    const actionsPage = await openActionsView(popup);

    // Grant clipboard permissions
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);

    // Click "Copy Script"
    await actionsPage.locator('#copy-script').click();
    await actionsPage.waitForTimeout(500);

    // Read clipboard content
    const clipboardText = await actionsPage.evaluate(() => navigator.clipboard.readText());
    expect(clipboardText.length).toBeGreaterThan(0);

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('actions view clear button removes all actions', async () => {
    const { popup, target } = await recordSomeActions();
    const actionsPage = await openActionsView(popup);

    // Verify there are rows before clearing
    const rowsBefore = await actionsPage.locator('#actions-list .script-line-row').count();
    expect(rowsBefore).toBeGreaterThan(0);

    // Click clear
    await actionsPage.locator('#clear-script').click();
    await actionsPage.waitForTimeout(1000);

    // After clearing, script-line-rows should be gone
    const rowsAfter = await actionsPage.locator('#actions-list .script-line-row').count();
    expect(rowsAfter).toBe(0);

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('actions view receives live updates from storage changes', async () => {
    // First open the actions view (empty after previous clear)
    const popup = await openPopup(context, extensionId);
    const actionsPage = await openActionsView(popup);

    // Verify it starts empty or with minimal content
    const rowsBefore = await actionsPage.locator('#actions-list .script-line-row').count();

    // Now record some actions while actions view is open
    const target = await openFixture(context, 'form-page.html');
    await target.bringToFront();
    await popup.bringToFront();
    await popup.locator('#record').click();
    await popup.waitForTimeout(1000);

    await target.bringToFront();
    await target.locator('#username').click();
    await target.locator('#username').fill('livetest');
    await target.waitForTimeout(300);

    await popup.bringToFront();
    await popup.locator('#stop').click();
    await popup.waitForTimeout(2000);

    // Bring actions view to front and check it updated
    await actionsPage.bringToFront();
    await actionsPage.waitForTimeout(1000);

    const rowsAfter = await actionsPage.locator('#actions-list .script-line-row').count();
    expect(rowsAfter).toBeGreaterThan(rowsBefore);

    await actionsPage.close();
    await popup.close();
    await target.close();
  });

  test('per-line copy button copies individual line', async () => {
    const { popup, target } = await recordSomeActions();
    const actionsPage = await openActionsView(popup);

    await context.grantPermissions(['clipboard-read', 'clipboard-write']);

    // Hover over the first row to reveal controls, then click copy
    const firstRow = actionsPage.locator('#actions-list .script-line-row').first();
    await firstRow.hover();
    await firstRow.locator('.av-icon-copy, [title*="copy" i]').first().click();
    await actionsPage.waitForTimeout(500);

    const clipboardText = await actionsPage.evaluate(() => navigator.clipboard.readText());
    expect(clipboardText.length).toBeGreaterThan(0);

    await actionsPage.close();
    await popup.close();
    await target.close();
  });
});
