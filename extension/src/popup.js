import logger from './logger.js';
import { IntroTour } from './intro.js';
import { t, getCurrentLanguage, setLanguage } from './translations.js';
import * as roboscope from './roboscope-client.js';

const debug = false;
const storage = chrome.storage.local;

let currentLanguage = 'en';
let introTour = null;
// Line-based script model: each line is { id, text }
let scriptLines = [];
let nextLineId = 1;

// ---------------------------------------------------------------------------
// State Machine
// ---------------------------------------------------------------------------
// Each state defines which elements are shown, hidden, active, and inactive.
// The toggle() function simply looks up the target state and applies it.

const STATE_CONFIG = {
  idle: {
    show: ['record', 'scan', 'xpath-console', 'status-field', 'script-container'],
    hide: ['pause', 'resume', 'stop', 'xpath-inputs', 'settings-panel'],
    active: [],
    inactive: ['xpath-console', 'settings', 'scan'],
    enableSettings: false,
    saveEnabled: false,
  },
  record: {
    show: ['pause', 'stop', 'status-field', 'script-container'],
    hide: ['record', 'scan', 'xpath-console', 'resume',
      'settings-panel', 'xpath-inputs'],
    active: [],
    inactive: ['xpath-console', 'settings', 'scan'],
    enableSettings: false,
    saveEnabled: false,
  },
  resume: {
    show: ['pause', 'stop', 'status-field', 'script-container'],
    hide: ['record', 'scan', 'xpath-console', 'resume',
      'settings-panel', 'xpath-inputs'],
    active: [],
    inactive: ['xpath-console', 'settings', 'scan'],
    enableSettings: false,
    saveEnabled: false,
  },
  pause: {
    show: ['resume', 'stop', 'script-container'],
    hide: ['record', 'scan', 'xpath-console', 'pause',
      'settings-panel', 'xpath-inputs'],
    active: [],
    inactive: [],
    enableSettings: false,
    saveEnabled: null, // don't change
  },
  stop: {
    show: ['record', 'scan', 'xpath-console', 'status-field', 'script-container'],
    hide: ['pause', 'resume', 'stop', 'xpath-inputs', 'settings-panel'],
    active: [],
    inactive: ['xpath-console', 'settings', 'scan'],
    enableSettings: false,
    saveEnabled: true,
  },
  save: {
    show: ['record', 'scan', 'xpath-console', 'status-field', 'script-container'],
    hide: ['pause', 'resume', 'stop', 'xpath-inputs', 'settings-panel'],
    active: [],
    inactive: ['xpath-console', 'settings', 'scan'],
    enableSettings: false,
    saveEnabled: true,
  },
  scan: {
    show: ['record', 'scan', 'xpath-console', 'status-field', 'script-container'],
    hide: ['pause', 'resume', 'stop', 'xpath-inputs', 'settings-panel'],
    active: ['scan'],
    inactive: ['xpath-console', 'settings'],
    enableSettings: false,
    saveEnabled: true,
  },
  settings: {
    show: ['record', 'scan', 'xpath-console', 'settings-panel'],
    hide: ['pause', 'resume', 'stop', 'script-container', 'xpath-inputs', 'status-field'],
    active: ['settings'],
    inactive: ['scan', 'xpath-console'],
    enableSettings: true,
    saveEnabled: null,
  },
  'xpath-console': {
    show: ['record', 'scan', 'xpath-console', 'xpath-inputs', 'status-field'],
    hide: ['pause', 'resume', 'stop', 'script-container', 'settings-panel'],
    active: ['xpath-console'],
    inactive: ['settings', 'scan'],
    enableSettings: false,
    saveEnabled: null,
  },
};

// ---------------------------------------------------------------------------
// Helpers: port-closed error detection
// ---------------------------------------------------------------------------
const PORT_CLOSED_PATTERNS = [
  'message port closed',
  'The message port closed before a response was received',
];

function isPortClosedError(err) {
  const msg = err && (err.message || JSON.stringify(err));
  return msg && PORT_CLOSED_PATTERNS.some(p => msg.includes(p));
}

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

const copyStatus = (className) => {
  const copyButton = document.getElementById('copy');
  if (!copyButton) {
    logger.debug('copyStatus: copy button not found');
    return;
  }
  copyButton.classList.add(className);
  setTimeout(() => { if (copyButton) copyButton.classList.remove(className); }, 3000);
};

async function copyToClipboard() {
  try {
    const scriptOutput = scriptLines.map(l => l.text).join('\n');
    await navigator.clipboard.writeText(scriptOutput);
    copyStatus('copy-ok');
  } catch (err) {
    copyStatus('copy-fail');
    logger.error('Copy failed:', err);
  }
}

// ---------------------------------------------------------------------------
// Line-based script model
// ---------------------------------------------------------------------------

function getTextFromScriptLines() {
  return scriptLines.map(l => l.text).join('\n');
}

function moveLine(index, delta) {
  const to = index + delta;
  if (to < 0 || to >= scriptLines.length) return;
  const [item] = scriptLines.splice(index, 1);
  scriptLines.splice(to, 0, item);
  storage.set({ script: getTextFromScriptLines() });
  renderScriptLines();
}

function deleteLine(index) {
  scriptLines.splice(index, 1);
  storage.set({ script: getTextFromScriptLines() });
  renderScriptLines();
}

function addLine(afterIndex = scriptLines.length) {
  const newLine = { id: nextLineId++, text: '' };
  scriptLines.splice(afterIndex, 0, newLine);
  storage.set({ script: getTextFromScriptLines() });
  renderScriptLines();
}

function renderScriptLines() {
  const container = document.getElementById('script-lines');
  if (!container) return;
  container.innerHTML = '';
  scriptLines.forEach((line, index) => {
    const row = document.createElement('div');
    row.className = 'script-line-row';
    row.dataset.lineId = String(line.id);

    const indexSpan = document.createElement('span');
    indexSpan.className = 'script-line-index';
    indexSpan.textContent = String(index + 1);

    const input = document.createElement('input');
    input.className = 'script-line-input';
    input.value = line.text;
    input.readOnly = true;

    const controls = document.createElement('div');
    controls.className = 'script-line-controls';

    const up = document.createElement('button');
    up.className = 'btn btn-small';
    up.textContent = '▲';
    up.title = 'Move up';
    up.addEventListener('click', () => moveLine(index, -1));

    const down = document.createElement('button');
    down.className = 'btn btn-small';
    down.textContent = '▼';
    down.title = 'Move down';
    down.addEventListener('click', () => moveLine(index, 1));

    const del = document.createElement('button');
    del.className = 'btn btn-small btn-danger';
    del.textContent = '×';
    del.title = 'Delete line';
    del.addEventListener('click', () => deleteLine(index));

    controls.appendChild(up);
    controls.appendChild(down);
    controls.appendChild(del);

    row.appendChild(indexSpan);
    row.appendChild(input);
    row.appendChild(controls);

    container.appendChild(row);
  });
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

function updateValueByMessage(elementId, message) {
  if (message === null || message === undefined) {
    logger.debug(`Tried to update value of ${elementId} by ${message}`);
    return;
  }
  // Guard: never display raw objects in the UI
  if (typeof message === 'object') {
    logger.debug(`Skipping object display for ${elementId}:`, message);
    return;
  }
  const text = String(message);
  if (elementId === '#script-output' || elementId === '#script-lines') {
    scriptLines = text.split('\n').map(ln => ({ id: nextLineId++, text: ln }));
    renderScriptLines();
  } else {
    const field = document.querySelector(elementId);
    if (field) field.innerText = text;
  }
}

function displayScript(message) {
  updateValueByMessage('#script-lines', message);
}

function displayStatus(message) {
  updateValueByMessage('#status-field', message);
}

function show(ids, visible) {
  ids.forEach((id) => {
    const elem = document.getElementById(id);
    if (elem) {
      visible ? elem.classList.remove('hidden') : elem.classList.add('hidden');
    } else {
      logger.debug('Tried to toggle visibility of non-existent element');
    }
  });
}

function hide(array) {
  show(array, false);
}

function enable(array, isEnabled) {
  array.forEach((id) => {
    const element = document.getElementById(id);
    if (!element) {
      logger.debug(`enable: element ${id} not found`);
      return;
    }
    if (isEnabled) element.classList.remove('disabled');
    else element.classList.add('disabled');
  });
}

function setActive(ids) {
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.add('btn-active');
  });
}

function setInactive(ids) {
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('btn-active');
  });
}

// ---------------------------------------------------------------------------
// State machine: toggle()
// ---------------------------------------------------------------------------

function toggle(e) {
  const action = e.target.id;
  logger.debug(action);

  // clear-script and copy don't change operating mode
  if (['clear-script', 'copy'].includes(action)) {
    // Just handle save/copy enable state
    if (action === 'clear-script') {
      document.getElementById('save').disabled = true;
      document.getElementById('copy').disabled = true;
    }
    return;
  }

  const config = STATE_CONFIG[action];
  if (!config) {
    logger.debug(`toggle: no state config for "${action}"`);
    return;
  }

  // Apply visibility
  show(config.show, true);
  hide(config.hide);

  // Apply active/inactive button styles
  setActive(config.active);
  setInactive(config.inactive);

  // Enable/disable settings panel
  enable(['settings-panel'], config.enableSettings);

  // Save/copy button state
  if (config.saveEnabled === true) {
    document.getElementById('save').disabled = false;
    document.getElementById('copy').disabled = false;
  } else if (config.saveEnabled === false) {
    document.getElementById('save').disabled = true;
    document.getElementById('copy').disabled = true;
  }
  // null = don't change

  // Apply extra state from the event object (settings, checkboxes, etc.)
  if (e.demo) document.getElementById('demo').checked = e.demo === true;
  if (e.verify) document.getElementById('verify').checked = e.verify === true;

  if (e.library_target) {
    const rfbrowserSelected = e.library_target === 'Browser';
    document.getElementById('target_rfbrowser').checked = rfbrowserSelected;
    document.getElementById('target_seleniumlibrary').checked = !rfbrowserSelected;
  }
  if (e.syntax) {
    const rpaSelected = e.syntax === 'rpa';
    document.getElementById('syntax_rpa').checked = rpaSelected;
    document.getElementById('syntax_testing').checked = !rpaSelected;
  }
}

// ---------------------------------------------------------------------------
// Busy state
// ---------------------------------------------------------------------------

function busy(e) {
  if (e.isBusy === true || e.isBusy === false) {
    ['scan', 'record', 'stop', 'save', 'copy', 'resume'].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) {
        logger.debug(`busy: element ${id} not found`);
        return;
      }
      el.disabled = e.isBusy;
    });
  }
}

// ---------------------------------------------------------------------------
// Messaging (native MV3 promises)
// ---------------------------------------------------------------------------

async function operation(e) {
  toggle(e);
  try {
    const resp = await chrome.runtime.sendMessage({ operation: e.target.id });
    // resp is { ok: true, ... } — don't display raw objects in status bar
    if (resp && typeof resp === 'object') {
      // Status updates come via storage.onChanged, no need to display here
    } else if (resp) {
      displayStatus(resp);
    }
  } catch (err) {
    if (isPortClosedError(err)) {
      logger.warn(
        `Runtime connection closed during operation ${e.target.id}:`,
        err.stack || err
      );
    } else {
      const errorMsg = err && (err.message || JSON.stringify(err));
      logger.error(`operation error (${e.target.id}):`, errorMsg);
      displayStatus(`Error: ${errorMsg}`);
    }
  }
}

async function xpathValidate() {
  const xpath = document.getElementById('textinput-xpath').value;
  try {
    const response = await chrome.runtime.sendMessage({
      operation: 'xpath-validate', xpath
    });
    logger.info('XPath validation response:', response);
  } catch (err) {
    if (isPortClosedError(err)) {
      logger.warn('Runtime connection closed during xpath-validate:', err.stack || err);
    } else {
      logger.error('xpath-validate error:', err.message || err);
    }
  }
}

async function updateSettings(_e) {
  const demo = document.getElementById('demo').checked;
  const verify = document.getElementById('verify').checked;
  const rfbrowserRadio = document.getElementById('target_rfbrowser');
  const rpaSyntax = document.getElementById('syntax_rpa');
  const target = rfbrowserRadio.checked ? 'Browser' : 'SeleniumLibrary';
  const syntax = rpaSyntax.checked ? 'rpa' : 'testing';

  try {
    const response = await chrome.runtime.sendMessage({
      operation: 'settings', demo, verify, target, syntax
    });
    logger.info('Settings updated:', response);
  } catch (err) {
    if (isPortClosedError(err)) {
      logger.warn('Runtime connection closed during settings update:', err.stack || err);
    } else {
      logger.error('settings error:', err.message || err);
    }
  }
}

function info() {
  if (introTour) {
    introTour.toggle();
  }
}

// ---------------------------------------------------------------------------
// Translations
// ---------------------------------------------------------------------------

function updateUITranslations(language) {
  // Buttons
  document.getElementById('record').textContent = t('record', language);
  document.getElementById('stop').textContent = t('stop', language);
  document.getElementById('resume').textContent = t('resume', language);
  document.getElementById('pause').textContent = t('pause', language);
  // scan and xpath-console are icon-only buttons — set title, not textContent
  document.getElementById('scan').title = t('scanPage', language);
  document.getElementById('xpath-console').title = t('validateXPath', language);
  document.getElementById('copy').textContent = t('copy', language);
  document.getElementById('save').textContent = t('download', language);
  document.getElementById('clear-script').textContent = t('clear', language);

  const addBtn = document.getElementById('add-line');
  if (addBtn) {
    addBtn.textContent = t('addLine', language);
    addBtn.title = t('addLineTitle', language);
  }

  // Titles
  document.getElementById('record').title = t('recordTitle', language);
  document.getElementById('stop').title = t('stopTitle', language);
  document.getElementById('resume').title = t('resumeTitle', language);
  document.getElementById('pause').title = t('pauseTitle', language);
  // scan/xpath-console titles already set above
  document.getElementById('info').title = t('infoTitle', language);
  document.getElementById('settings').title = t('settingsTitle', language);
  document.getElementById('copy').title = t('copyTitle', language);
  document.getElementById('save').title = t('downloadTitle', language);
  document.getElementById('clear-script').title = t('clearTitle', language);

  // Data-intro
  document.getElementById('record').setAttribute('data-intro', t('recordIntro', language));
  document.getElementById('scan').setAttribute('data-intro', t('scanIntro', language));
  document.getElementById('xpath-console').setAttribute('data-intro', t('xpathIntro', language));
  document.getElementById('settings').setAttribute('data-intro', t('settingsIntro', language));

  // Placeholder
  document.getElementById('textinput-xpath').placeholder = t('xpathPlaceholder', language);

  // Settings Panel
  document.getElementById('language-label').textContent = t('language', language);
  document.getElementById('target-library-label').textContent = t('targetLibrary', language);
  document.getElementById('selenium-label').textContent = t('selenium', language);
  document.getElementById('rfbrowser-label').textContent = t('rfBrowser', language);
  document.getElementById('target-syntax-label').textContent = t('targetSyntax', language);
  document.getElementById('rpa-label').textContent = t('rpa', language);
  document.getElementById('test-automation-label').textContent = t('testAutomation', language);
  document.getElementById('advanced-settings-label').textContent = t('advancedSettings', language);
  document.getElementById('demo-label').textContent = t('addSleep', language);
  document.getElementById('verify-label').textContent = t('checkPageContains', language);
}

async function changeLanguage(e) {
  const newLanguage = e.target.value;
  currentLanguage = newLanguage;
  setLanguage(newLanguage);
  updateUITranslations(newLanguage);
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  try {
    currentLanguage = await getCurrentLanguage();

    const state = await storage.get({
      message: 'Record or Scan',
      operation: 'idle',
      canSave: false,
      isBusy: false,
      demo: false,
      verify: false,
      target: 'Browser',
      syntax: 'rpa',
      locators: [],
      script: '',
    });

    if (state.message === 'Record or Scan') {
      state.message = t('recordOrScan', currentLanguage);
    }

    displayStatus(state.message);
    displayScript(state.script);

    updateUITranslations(currentLanguage);

    document.getElementById(`lang_${currentLanguage}`).checked = true;

    // Prevent showing settings panel automatically on load
    const initialOperation = state.operation === 'settings' ? 'idle' : state.operation;
    toggle({
      target: { id: initialOperation },
      canSave: state.canSave,
      isBusy: state.isBusy,
      demo: state.demo,
      verify: state.verify,
      library_target: state.target,
      syntax: state.syntax,
    });

    // Ensure settings panel is hidden on initial load regardless
    hide(['settings-panel']);

    if (debug) document.getElementById('textarea-log').classList.remove('hidden');

    [
      'record', 'resume', 'stop', 'pause', 'save', 'scan',
      'xpath-console', 'settings', 'clear-script',
    ].forEach((id) => {
      document.getElementById(id).addEventListener('click', operation);
    });

    document.getElementById('copy').addEventListener('click', copyToClipboard);

    ['demo', 'verify'].forEach((id) => {
      document.getElementById(id).addEventListener('change', updateSettings);
    });

    ['target', 'syntax'].forEach((cls) => {
      Array.from(document.getElementsByClassName(cls))
        .forEach(elem => elem.addEventListener('change', updateSettings));
    });

    Array.from(document.getElementsByClassName('language-option'))
      .forEach(elem => elem.addEventListener('change', changeLanguage));

    document.getElementById('textinput-xpath').addEventListener('input', xpathValidate);

    const addBtn = document.getElementById('add-line');
    if (addBtn) addBtn.addEventListener('click', () => addLine());

    introTour = new IntroTour();
    introTour.init();

    document.getElementById('info').addEventListener('click', info);

    const openActionsBtn = document.getElementById('open-actions-view');
    if (openActionsBtn) {
      openActionsBtn.addEventListener('click', () => {
        try {
          chrome.runtime.sendMessage({ operation: 'open-actions-view' });
        } catch (err) {
          logger.warn('Could not send open-actions-view message:', err);
        }
      });
    }

    // RoboScope connection indicator
    const roboscopeBar = document.getElementById('roboscope-bar');
    const roboscopeLabel = document.getElementById('roboscope-label');
    const configured = await roboscope.isConfigured();
    if (configured) {
      roboscopeBar.classList.remove('hidden');
      const { connected } = await storage.get({ connected: false });
      if (connected) {
        roboscopeBar.classList.add('connected');
        roboscopeBar.classList.remove('disconnected');
        roboscopeLabel.textContent = 'RoboScope connected';
      } else {
        roboscopeBar.classList.add('disconnected');
        roboscopeBar.classList.remove('connected');
        roboscopeLabel.textContent = 'RoboScope disconnected';
      }
      roboscopeBar.addEventListener('click', () => {
        chrome.runtime.openOptionsPage();
      });
    }
  } catch (err) {
    logger.error('Init failed:', err);
    console.error('RF Recorder init failed:', err);
  }
}, false);

chrome.storage.onChanged.addListener((changes) => {
  logger.debug('Localstorage event, changes: ', changes);
  for (const key in changes) {
    const newValue = changes[key].newValue;
    if (key === 'isBusy') busy({ isBusy: newValue });
    if (key === 'message') displayStatus(newValue);
    if (key === 'script') displayScript(newValue || '');
  }
});
