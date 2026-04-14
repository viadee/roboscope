/**
 * context-menu.js — Right-click context menu for quick actions.
 *
 * Adds context menu items for:
 * - Copy best selector
 * - Insert Click / Fill Text / assertions / waits
 * - Control structures (IF, FOR, WHILE, TRY)
 */

import logger from './logger.js';

const storage = chrome.storage.local;

// ---------------------------------------------------------------------------
// Menu structure
// ---------------------------------------------------------------------------

const MENU_ITEMS = [
  { id: 'rfr-separator-top', type: 'separator' },
  {
    id: 'rfr-copy-selector',
    title: '📋 Copy Best Selector',
    contexts: ['all'],
  },
  { id: 'rfr-separator-actions', type: 'separator' },
  {
    id: 'rfr-add-click',
    title: '👆 Add Click',
    contexts: ['all'],
  },
  {
    id: 'rfr-add-fill',
    title: '✏️ Add Fill Text...',
    contexts: ['editable'],
  },
  {
    id: 'rfr-add-hover',
    title: '🔍 Add Hover',
    contexts: ['all'],
  },
  // Assertions submenu
  {
    id: 'rfr-assertions',
    title: '✅ Add Assertion',
    contexts: ['all'],
  },
  {
    id: 'rfr-assert-visible',
    title: 'Element Should Be Visible',
    parentId: 'rfr-assertions',
    contexts: ['all'],
  },
  {
    id: 'rfr-assert-text',
    title: 'Assert Text Equals...',
    parentId: 'rfr-assertions',
    contexts: ['all'],
  },
  {
    id: 'rfr-assert-count',
    title: 'Assert Element Count == 1',
    parentId: 'rfr-assertions',
    contexts: ['all'],
  },
  {
    id: 'rfr-assert-contains',
    title: 'Page Contains Element',
    parentId: 'rfr-assertions',
    contexts: ['all'],
  },
  // Waits submenu
  {
    id: 'rfr-waits',
    title: '⏳ Add Wait',
    contexts: ['all'],
  },
  {
    id: 'rfr-wait-visible',
    title: 'Wait Until Visible',
    parentId: 'rfr-waits',
    contexts: ['all'],
  },
  {
    id: 'rfr-wait-hidden',
    title: 'Wait Until Hidden',
    parentId: 'rfr-waits',
    contexts: ['all'],
  },
  {
    id: 'rfr-wait-attached',
    title: 'Wait Until Attached',
    parentId: 'rfr-waits',
    contexts: ['all'],
  },
  // Control structures submenu
  {
    id: 'rfr-control',
    title: '🔀 Control Structure',
    contexts: ['all'],
  },
  {
    id: 'rfr-control-if',
    title: 'IF / ELSE IF / ELSE / END',
    parentId: 'rfr-control',
    contexts: ['all'],
  },
  {
    id: 'rfr-control-for',
    title: 'FOR / END',
    parentId: 'rfr-control',
    contexts: ['all'],
  },
  {
    id: 'rfr-control-while',
    title: 'WHILE / END',
    parentId: 'rfr-control',
    contexts: ['all'],
  },
  {
    id: 'rfr-control-try',
    title: 'TRY / EXCEPT / END',
    parentId: 'rfr-control',
    contexts: ['all'],
  },
];

// ---------------------------------------------------------------------------
// Create menus
// ---------------------------------------------------------------------------

export function createContextMenus() {
  // Remove any existing menus first
  chrome.contextMenus.removeAll(() => {
    for (const item of MENU_ITEMS) {
      const opts = {
        id: item.id,
        contexts: item.contexts || ['all'],
      };
      if (item.type === 'separator') {
        opts.type = 'separator';
      } else {
        opts.title = item.title;
      }
      if (item.parentId) opts.parentId = item.parentId;
      chrome.contextMenus.create(opts);
    }
    logger.info('Context menus created');
  });
}

// ---------------------------------------------------------------------------
// Get selector from clicked element (runs in content script context)
// ---------------------------------------------------------------------------

async function getSelectorFromTab(tabId, frameId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId, frameIds: frameId ? [frameId] : undefined },
      func: () => {
        // This runs in the page context
        const el = document.activeElement
          || document.querySelector(':hover');
        if (!el || el === document.body) return null;

        // Try ID first
        if (el.id) return `//*[@id="${el.id}"]`;

        // Try name
        if (el.name) {
          return `//*[@name="${el.name}"]`;
        }

        // Try data-testid
        if (el.dataset.testid) {
          return `//*[@data-testid="${el.dataset.testid}"]`;
        }

        // Build XPath from tag + text or attributes
        const tag = el.tagName.toLowerCase();
        const text = el.textContent?.trim();
        if (text && text.length < 50 && text.length > 0) {
          return `//${tag}[contains(text(),"${
            text.replace(/"/g, "'")
          }")]`;
        }

        // Fallback: class-based
        if (el.className && typeof el.className === 'string') {
          const cls = el.className.split(/\s+/)[0];
          if (cls) return `//${tag}[@class="${cls}"]`;
        }

        return null;
      },
    });
    return results?.[0]?.result || null;
  } catch (err) {
    logger.warn('Could not get selector:', err);
    return null;
  }
}

/**
 * Get the text content of the right-clicked element.
 */
async function getElementText(tabId, frameId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId, frameIds: frameId ? [frameId] : undefined },
      func: () => {
        const el = document.activeElement
          || document.querySelector(':hover');
        if (!el) return '';
        return el.textContent?.trim()?.substring(0, 200) || '';
      },
    });
    return results?.[0]?.result || '';
  } catch (err) {
    logger.warn('Could not get element text:', err);
    return '';
  }
}

// ---------------------------------------------------------------------------
// Append a script line to storage
// ---------------------------------------------------------------------------

async function appendScriptLine(line) {
  const data = await storage.get({ script: '' });
  const existing = data.script || '';
  const newScript = existing
    ? existing + '\n' + line
    : line;
  await storage.set({
    script: newScript,
    canSave: true,
    operation: 'stop',
  });
  logger.info('Appended script line:', line);
}

async function appendMultipleLines(lines) {
  const data = await storage.get({ script: '' });
  const existing = data.script || '';
  const newScript = existing
    ? existing + '\n' + lines.join('\n')
    : lines.join('\n');
  await storage.set({
    script: newScript,
    canSave: true,
    operation: 'stop',
  });
}

// ---------------------------------------------------------------------------
// Build RF lines based on current library
// ---------------------------------------------------------------------------

async function getLibrary() {
  const data = await storage.get({ target: 'Browser' });
  return data.target;
}

function buildActionLine(library, keyword, args) {
  const parts = [keyword, ...args].filter(Boolean);
  return parts.join('    ');
}

// ---------------------------------------------------------------------------
// Handle menu clicks
// ---------------------------------------------------------------------------

export function handleContextMenuClick(info, tab) {
  const menuId = info.menuItemId;
  const tabId = tab?.id;
  const frameId = info.frameId;

  if (!tabId) {
    logger.warn('No tab for context menu action');
    return;
  }

  (async () => {
    const selector = await getSelectorFromTab(tabId, frameId);
    const library = await getLibrary();

    if (!selector && !menuId.startsWith('rfr-control')) {
      logger.warn('Could not determine selector for element');
      await storage.set({
        message: 'Could not determine selector for element',
      });
      return;
    }

    switch (menuId) {
    case 'rfr-copy-selector':
      // Copy selector to clipboard via content script
      await chrome.scripting.executeScript({
        target: { tabId },
        func: (sel) => navigator.clipboard.writeText(sel),
        args: [selector],
      });
      await storage.set({ message: `Copied: ${selector}` });
      break;

    case 'rfr-add-click':
      if (library === 'Browser') {
        await appendScriptLine(
          buildActionLine(library, 'Click', [selector])
        );
      } else {
        await appendScriptLine(
          buildActionLine(library, 'Click Element', [selector])
        );
      }
      await storage.set({ message: `Added Click on ${selector}` });
      break;

    case 'rfr-add-fill': {
      // Prompt for text value via content script
      const value = await promptInTab(tabId, 'Enter text value:');
      if (value === null) return;
      if (library === 'Browser') {
        await appendScriptLine(
          buildActionLine(library, 'Fill Text', [selector, value])
        );
      } else {
        await appendScriptLine(
          buildActionLine(library, 'Input Text', [selector, value])
        );
      }
      await storage.set({
        message: `Added Fill Text on ${selector}`,
      });
      break;
    }

    case 'rfr-add-hover':
      if (library === 'Browser') {
        await appendScriptLine(
          buildActionLine(library, 'Hover', [selector])
        );
      } else {
        await appendScriptLine(
          buildActionLine(library, 'Mouse Over', [selector])
        );
      }
      break;

    // Assertions
    case 'rfr-assert-visible':
      if (library === 'Browser') {
        await appendScriptLine(buildActionLine(
          library, 'Wait For Elements State',
          [selector, 'visible']
        ));
      } else {
        await appendScriptLine(buildActionLine(
          library, 'Element Should Be Visible', [selector]
        ));
      }
      await storage.set({ message: 'Added visibility assertion' });
      break;

    case 'rfr-assert-text': {
      const elText = await getElementText(tabId, frameId);
      if (library === 'Browser') {
        await appendScriptLine(buildActionLine(
          library, 'Get Text', [selector, '==', elText]
        ));
      } else {
        await appendScriptLine(buildActionLine(
          library, 'Element Text Should Be', [selector, elText]
        ));
      }
      await storage.set({ message: 'Added text assertion' });
      break;
    }

    case 'rfr-assert-count':
      if (library === 'Browser') {
        await appendScriptLine(buildActionLine(
          library, 'Get Element Count', [selector, '==', '1']
        ));
      } else {
        await appendScriptLine(buildActionLine(
          library, 'Page Should Contain Element', [selector]
        ));
      }
      await storage.set({ message: 'Added element count assertion' });
      break;

    case 'rfr-assert-contains':
      if (library === 'Browser') {
        await appendScriptLine(buildActionLine(
          library, 'Get Element Count',
          [selector, '>=', '1']
        ));
      } else {
        await appendScriptLine(buildActionLine(
          library, 'Page Should Contain Element', [selector]
        ));
      }
      await storage.set({ message: 'Added contains assertion' });
      break;

    // Waits
    case 'rfr-wait-visible':
      if (library === 'Browser') {
        await appendScriptLine(buildActionLine(
          library, 'Wait For Elements State',
          [selector, 'visible', '10s']
        ));
      } else {
        await appendScriptLine(buildActionLine(
          library, 'Wait Until Element Is Visible',
          [selector, '10s']
        ));
      }
      await storage.set({ message: 'Added wait for visible' });
      break;

    case 'rfr-wait-hidden':
      if (library === 'Browser') {
        await appendScriptLine(buildActionLine(
          library, 'Wait For Elements State',
          [selector, 'hidden', '10s']
        ));
      } else {
        await appendScriptLine(buildActionLine(
          library, 'Wait Until Element Is Not Visible',
          [selector, '10s']
        ));
      }
      break;

    case 'rfr-wait-attached':
      if (library === 'Browser') {
        await appendScriptLine(buildActionLine(
          library, 'Wait For Elements State',
          [selector, 'attached', '10s']
        ));
      } else {
        await appendScriptLine(buildActionLine(
          library, 'Wait Until Page Contains Element',
          [selector, '10s']
        ));
      }
      break;

    // Control structures
    case 'rfr-control-if':
      await appendMultipleLines([
        '    IF    ${condition}',
        '        Log    condition is true',
        '    ELSE IF    ${other_condition}',
        '        Log    other condition',
        '    ELSE',
        '        Log    fallback',
        '    END',
      ]);
      await storage.set({ message: 'Added IF/ELSE structure' });
      break;

    case 'rfr-control-for':
      await appendMultipleLines([
        '    FOR    ${item}    IN    @{items}',
        '        Log    ${item}',
        '    END',
      ]);
      await storage.set({ message: 'Added FOR loop' });
      break;

    case 'rfr-control-while':
      await appendMultipleLines([
        '    WHILE    ${condition}    limit=100',
        '        Log    iteration',
        '    END',
      ]);
      await storage.set({ message: 'Added WHILE loop' });
      break;

    case 'rfr-control-try':
      await appendMultipleLines([
        '    TRY',
        '        Log    try block',
        '    EXCEPT    AS    ${error}',
        '        Log    Error: ${error}',
        '    FINALLY',
        '        Log    cleanup',
        '    END',
      ]);
      await storage.set({ message: 'Added TRY/EXCEPT structure' });
      break;

    default:
      logger.debug('Unknown context menu id:', menuId);
    }
  })();
}

/**
 * Prompt the user for input via the content script.
 */
async function promptInTab(tabId, message) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (msg) => window.prompt(msg),
      args: [message],
    });
    return results?.[0]?.result ?? null;
  } catch (err) {
    logger.warn('Prompt failed:', err);
    return null;
  }
}
