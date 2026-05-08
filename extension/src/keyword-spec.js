/**
 * keyword-spec.js — Keyword metadata for RF Browser and SeleniumLibrary.
 *
 * Maps keyword names to their parameter definitions, enabling structured
 * editing with named parameter fields in the actions view.
 */

const BROWSER_KEYWORDS = {
  'New Page': {
    params: [
      { name: 'url', type: 'url', placeholder: 'https://example.com' },
      { name: 'browser', type: 'select', options: ['chromium', 'firefox', 'webkit'], optional: true },
    ],
    category: 'navigation',
    icon: '🌐',
  },
  'Go To': {
    params: [{ name: 'url', type: 'url', placeholder: 'https://...' }],
    category: 'navigation',
    icon: '🌐',
  },
  'Click': {
    params: [
      { name: 'selector', type: 'locator', placeholder: '//button[@id="..."]' },
    ],
    category: 'interaction',
    icon: '👆',
  },
  'Fill Text': {
    params: [
      { name: 'selector', type: 'locator', placeholder: '//input[@id="..."]' },
      { name: 'text', type: 'text', placeholder: 'value' },
    ],
    category: 'interaction',
    icon: '✏️',
  },
  'Type Text': {
    params: [
      { name: 'selector', type: 'locator', placeholder: '//input[@id="..."]' },
      { name: 'text', type: 'text', placeholder: 'value' },
      { name: 'delay', type: 'text', placeholder: '50ms', optional: true },
    ],
    category: 'interaction',
    icon: '⌨️',
  },
  'Check Checkbox': {
    params: [{ name: 'selector', type: 'locator' }],
    category: 'interaction',
    icon: '☑️',
  },
  'Uncheck Checkbox': {
    params: [{ name: 'selector', type: 'locator' }],
    category: 'interaction',
    icon: '⬜',
  },
  'Select Options By': {
    params: [
      { name: 'selector', type: 'locator' },
      { name: 'attribute', type: 'select', options: ['value', 'label', 'text', 'index'] },
      { name: 'values', type: 'text', placeholder: 'option value' },
    ],
    category: 'interaction',
    icon: '📋',
  },
  'Hover': {
    params: [{ name: 'selector', type: 'locator' }],
    category: 'interaction',
    icon: '🔍',
  },
  'Focus': {
    params: [{ name: 'selector', type: 'locator' }],
    category: 'interaction',
    icon: '🎯',
  },
  'Press Keys': {
    params: [
      { name: 'selector', type: 'locator' },
      { name: 'keys', type: 'text', placeholder: 'Enter, Tab, ...' },
    ],
    category: 'interaction',
    icon: '⌨️',
  },
  'Upload File By Selector': {
    params: [
      { name: 'selector', type: 'locator' },
      { name: 'path', type: 'text', placeholder: '/path/to/file' },
    ],
    category: 'interaction',
    icon: '📁',
  },
  'Wait For Elements State': {
    params: [
      { name: 'selector', type: 'locator' },
      {
        name: 'state', type: 'select', optional: true,
        options: ['visible', 'hidden', 'attached', 'detached', 'stable'],
      },
      { name: 'timeout', type: 'text', placeholder: '10s', optional: true },
    ],
    category: 'wait',
    icon: '⏳',
  },
  'Wait For Condition': {
    params: [
      { name: 'condition', type: 'text', placeholder: 'element.visible' },
      { name: 'timeout', type: 'text', placeholder: '10s', optional: true },
    ],
    category: 'wait',
    icon: '⏳',
  },
  'Get Text': {
    params: [
      { name: 'selector', type: 'locator' },
      {
        name: 'assertion_operator', type: 'select', optional: true,
        options: ['==', '!=', 'contains', 'matches', 'starts', 'ends'],
      },
      { name: 'assertion_expected', type: 'text', optional: true },
    ],
    category: 'assertion',
    icon: '📖',
  },
  'Get Element Count': {
    params: [
      { name: 'selector', type: 'locator' },
      { name: 'assertion_operator', type: 'select', options: ['==', '!=', '>', '<', '>=', '<='], optional: true },
      { name: 'assertion_expected', type: 'text', optional: true },
    ],
    category: 'assertion',
    icon: '🔢',
  },
  'Get Url': {
    params: [
      { name: 'assertion_operator', type: 'select', options: ['==', '!=', 'contains', 'matches'], optional: true },
      { name: 'assertion_expected', type: 'text', optional: true },
    ],
    category: 'assertion',
    icon: '🔗',
  },
  'Get Title': {
    params: [
      { name: 'assertion_operator', type: 'select', options: ['==', '!=', 'contains'], optional: true },
      { name: 'assertion_expected', type: 'text', optional: true },
    ],
    category: 'assertion',
    icon: '📄',
  },
  'Take Screenshot': {
    params: [
      { name: 'filename', type: 'text', placeholder: 'screenshot.png', optional: true },
    ],
    category: 'utility',
    icon: '📸',
  },
  'Sleep': {
    params: [{ name: 'duration', type: 'text', placeholder: '3s' }],
    category: 'utility',
    icon: '💤',
  },
  'Close Browser': {
    params: [],
    category: 'navigation',
    icon: '❌',
  },
  'Close Page': {
    params: [],
    category: 'navigation',
    icon: '❌',
  },
};

const SELENIUM_KEYWORDS = {
  'Open Browser': {
    params: [
      { name: 'url', type: 'url', placeholder: 'https://example.com' },
      { name: 'browser', type: 'select', options: ['chrome', 'firefox', 'edge', 'safari'], optional: true },
    ],
    category: 'navigation',
    icon: '🌐',
  },
  'Go To': {
    params: [{ name: 'url', type: 'url', placeholder: 'https://...' }],
    category: 'navigation',
    icon: '🌐',
  },
  'Click Element': {
    params: [{ name: 'locator', type: 'locator' }],
    category: 'interaction',
    icon: '👆',
  },
  'Input Text': {
    params: [
      { name: 'locator', type: 'locator' },
      { name: 'text', type: 'text', placeholder: 'value' },
    ],
    category: 'interaction',
    icon: '✏️',
  },
  'Clear Element Text': {
    params: [{ name: 'locator', type: 'locator' }],
    category: 'interaction',
    icon: '🧹',
  },
  'Select From List By Value': {
    params: [
      { name: 'locator', type: 'locator' },
      { name: 'values', type: 'text' },
    ],
    category: 'interaction',
    icon: '📋',
  },
  'Select From List By Label': {
    params: [
      { name: 'locator', type: 'locator' },
      { name: 'labels', type: 'text' },
    ],
    category: 'interaction',
    icon: '📋',
  },
  'Select Checkbox': {
    params: [{ name: 'locator', type: 'locator' }],
    category: 'interaction',
    icon: '☑️',
  },
  'Unselect Checkbox': {
    params: [{ name: 'locator', type: 'locator' }],
    category: 'interaction',
    icon: '⬜',
  },
  'Mouse Over': {
    params: [{ name: 'locator', type: 'locator' }],
    category: 'interaction',
    icon: '🔍',
  },
  'Press Keys': {
    params: [
      { name: 'locator', type: 'locator' },
      { name: 'keys', type: 'text' },
    ],
    category: 'interaction',
    icon: '⌨️',
  },
  'Wait Until Element Is Visible': {
    params: [
      { name: 'locator', type: 'locator' },
      { name: 'timeout', type: 'text', placeholder: '10s', optional: true },
    ],
    category: 'wait',
    icon: '⏳',
  },
  'Wait Until Page Contains Element': {
    params: [
      { name: 'locator', type: 'locator' },
      { name: 'timeout', type: 'text', placeholder: '10s', optional: true },
    ],
    category: 'wait',
    icon: '⏳',
  },
  'Element Should Be Visible': {
    params: [{ name: 'locator', type: 'locator' }],
    category: 'assertion',
    icon: '👁️',
  },
  'Page Should Contain Element': {
    params: [{ name: 'locator', type: 'locator' }],
    category: 'assertion',
    icon: '🔢',
  },
  'Element Text Should Be': {
    params: [
      { name: 'locator', type: 'locator' },
      { name: 'expected', type: 'text' },
    ],
    category: 'assertion',
    icon: '📖',
  },
  'Title Should Be': {
    params: [{ name: 'title', type: 'text' }],
    category: 'assertion',
    icon: '📄',
  },
  'Location Should Be': {
    params: [{ name: 'url', type: 'url' }],
    category: 'assertion',
    icon: '🔗',
  },
  'Capture Page Screenshot': {
    params: [{ name: 'filename', type: 'text', optional: true }],
    category: 'utility',
    icon: '📸',
  },
  'Close Browser': {
    params: [],
    category: 'navigation',
    icon: '❌',
  },
  'Sleep': {
    params: [{ name: 'time', type: 'text', placeholder: '3s' }],
    category: 'utility',
    icon: '💤',
  },
};

const CATEGORY_COLORS = {
  navigation: '#3B82F6',
  interaction: '#10B981',
  wait: '#F59E0B',
  assertion: '#8B5CF6',
  utility: '#6B7280',
};

/**
 * Parse a raw Robot Framework line into keyword + arguments.
 * RF uses 2+ spaces (or tabs) as separator.
 */
export function parseLine(line) {
  if (!line || !line.trim()) return null;
  const trimmed = line.replace(/^\s+/, '');
  // Split on 2+ spaces or tab
  const parts = trimmed.split(/\s{2,}|\t+/).filter(p => p.length > 0);
  if (parts.length === 0) return null;
  return {
    keyword: parts[0],
    args: parts.slice(1),
    raw: line,
  };
}

/**
 * Look up keyword spec for the given keyword name and library.
 */
export function getKeywordSpec(keywordName, library) {
  const specs = library === 'Browser' ? BROWSER_KEYWORDS : SELENIUM_KEYWORDS;
  return specs[keywordName] || null;
}

/**
 * Get all keyword names for a library.
 */
export function getKeywordNames(library) {
  const specs = library === 'Browser' ? BROWSER_KEYWORDS : SELENIUM_KEYWORDS;
  return Object.keys(specs);
}

/**
 * Get the category color for a keyword.
 */
export function getCategoryColor(keywordName, library) {
  const spec = getKeywordSpec(keywordName, library);
  if (!spec) return CATEGORY_COLORS.utility;
  return CATEGORY_COLORS[spec.category] || CATEGORY_COLORS.utility;
}

/**
 * Rebuild a raw RF line from keyword + args.
 */
export function buildLine(keyword, args) {
  const parts = [keyword, ...args].filter(p => p && p.trim());
  return '    ' + parts.join('    ');
}

export { BROWSER_KEYWORDS, SELENIUM_KEYWORDS, CATEGORY_COLORS };
