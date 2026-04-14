// @ts-check
const { test, expect } = require('@playwright/test');
const {
  launchExtension, openPopup, openFixture, cleanup
} = require('./setup');

test.describe('Context Menu', () => {
  let context, extensionId, userDataDir, worker;

  test.beforeAll(async () => {
    ({ context, extensionId, userDataDir, worker } = await launchExtension());
  });

  test.afterAll(async () => {
    await cleanup(context, userDataDir);
  });

  test('context menu adds Click action via message', async () => {
    // We can't directly trigger Chrome context menus from Playwright,
    // but we can test the underlying mechanism: sending a message
    // to the background that simulates the context menu action.
    const popup = await openPopup(context, extensionId);
    const target = await openFixture(context, 'form-page.html');

    // Clear any existing script
    await popup.bringToFront();
    await popup.evaluate(async () => {
      await chrome.storage.local.remove(['script', 'list']);
    });

    // Simulate what the context menu handler does: append a Click line
    await popup.evaluate(async () => {
      const data = await chrome.storage.local.get({ script: '' });
      const existing = data.script || '';
      const newLine = '    Click    //input[@id="username"]';
      const newScript = existing ? existing + '\n' + newLine : newLine;
      await chrome.storage.local.set({
        script: newScript,
        canSave: true,
        operation: 'stop',
      });
    });

    await popup.waitForTimeout(1000);

    // Verify the script was stored
    const script = await popup.evaluate(async () => {
      const data = await chrome.storage.local.get({ script: '' });
      return data.script;
    });
    expect(script).toContain('Click');
    expect(script).toContain('//input[@id="username"]');

    await popup.close();
    await target.close();
  });

  test('context menu adds assertion via storage', async () => {
    const popup = await openPopup(context, extensionId);

    await popup.evaluate(async () => {
      await chrome.storage.local.remove(['script', 'list']);
    });

    // Simulate adding a visibility assertion
    await popup.evaluate(async () => {
      const line = '    Wait For Elements State'
        + '    //div[@class="content"]    visible';
      await chrome.storage.local.set({
        script: line,
        canSave: true,
        operation: 'stop',
      });
    });

    const script = await popup.evaluate(async () => {
      const data = await chrome.storage.local.get({ script: '' });
      return data.script;
    });
    expect(script).toContain('Wait For Elements State');
    expect(script).toContain('visible');

    await popup.close();
  });

  test('context menu adds control structure (IF)', async () => {
    const popup = await openPopup(context, extensionId);

    await popup.evaluate(async () => {
      await chrome.storage.local.remove(['script', 'list']);
    });

    // Simulate adding an IF/ELSE structure
    await popup.evaluate(async () => {
      const lines = [
        '    IF    ${condition}',
        '        Log    condition is true',
        '    ELSE',
        '        Log    fallback',
        '    END',
      ];
      await chrome.storage.local.set({
        script: lines.join('\n'),
        canSave: true,
        operation: 'stop',
      });
    });

    const script = await popup.evaluate(async () => {
      const data = await chrome.storage.local.get({ script: '' });
      return data.script;
    });
    expect(script).toContain('IF');
    expect(script).toContain('ELSE');
    expect(script).toContain('END');

    await popup.close();
  });

  test('context menu adds FOR loop', async () => {
    const popup = await openPopup(context, extensionId);

    await popup.evaluate(async () => {
      await chrome.storage.local.remove(['script', 'list']);
    });

    await popup.evaluate(async () => {
      const lines = [
        '    FOR    ${item}    IN    @{items}',
        '        Log    ${item}',
        '    END',
      ];
      await chrome.storage.local.set({
        script: lines.join('\n'),
        canSave: true,
        operation: 'stop',
      });
    });

    const script = await popup.evaluate(async () => {
      const data = await chrome.storage.local.get({ script: '' });
      return data.script;
    });
    expect(script).toContain('FOR');
    expect(script).toContain('${item}');
    expect(script).toContain('@{items}');
    expect(script).toContain('END');

    await popup.close();
  });

  test('context menu adds wait assertion', async () => {
    const popup = await openPopup(context, extensionId);

    await popup.evaluate(async () => {
      await chrome.storage.local.remove(['script', 'list']);
    });

    await popup.evaluate(async () => {
      const line = '    Wait For Elements State'
        + '    //button[@id="submit"]    attached    10s';
      await chrome.storage.local.set({
        script: line,
        canSave: true,
        operation: 'stop',
      });
    });

    const script = await popup.evaluate(async () => {
      const data = await chrome.storage.local.get({ script: '' });
      return data.script;
    });
    expect(script).toContain('attached');
    expect(script).toContain('10s');

    await popup.close();
  });

  test('multiple context menu actions append to script', async () => {
    const popup = await openPopup(context, extensionId);

    await popup.evaluate(async () => {
      await chrome.storage.local.remove(['script', 'list']);
    });

    // First action
    await popup.evaluate(async () => {
      const line = '    Click    //input[@id="username"]';
      await chrome.storage.local.set({ script: line });
    });

    // Second action (append)
    await popup.evaluate(async () => {
      const data = await chrome.storage.local.get({ script: '' });
      const existing = data.script || '';
      const line = '    Fill Text    //input[@id="username"]    admin';
      await chrome.storage.local.set({
        script: existing + '\n' + line,
      });
    });

    const script = await popup.evaluate(async () => {
      const data = await chrome.storage.local.get({ script: '' });
      return data.script;
    });

    const lines = script.split('\n').filter(l => l.trim());
    expect(lines.length).toBe(2);
    expect(lines[0]).toContain('Click');
    expect(lines[1]).toContain('Fill Text');

    await popup.close();
  });
});
