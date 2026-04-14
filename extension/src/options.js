import { t, getCurrentLanguage, setLanguage } from './translations.js';
import * as roboscope from './roboscope-client.js';

const storage = chrome.storage.local;

let currentLanguage = 'en';

export function update() {
  const values = document.getElementById('custom-locators').value;
  const array = values ? values.split(',') : ['for', 'name', 'id', 'title', 'href', 'class'];
  storage.set({ locators: array });
}

/**
 * Update UI translations
 */
function updateUITranslations(language) {
  document.getElementById('language-label').textContent = t('language', language);
  document.getElementById('custom-locators-heading').textContent = t('customLocators', language);
  document.getElementById('hint').textContent = t('customLocatorsHint', language);
  document.getElementById('reset').textContent = t('reset', language);
  document.getElementById('update').textContent = t('update', language);
}

/**
 * Handle language change
 */
async function changeLanguage(e) {
  const newLanguage = e.target.value;
  currentLanguage = newLanguage;
  setLanguage(newLanguage);
  updateUITranslations(newLanguage);
}

// ---------------------------------------------------------------------------
// RoboScope connection settings
// ---------------------------------------------------------------------------

function showStatus(message, type) {
  const el = document.getElementById('roboscope-status');
  el.textContent = message;
  el.className = `roboscope-status roboscope-status-${type}`;
  el.classList.remove('hidden');
}

function hideStatus() {
  document.getElementById('roboscope-status').classList.add('hidden');
}

async function loadRoboscopeSettings() {
  const settings = await roboscope.getSettings();
  document.getElementById('roboscope-url').value = settings.serverUrl || '';
  document.getElementById('roboscope-token').value = settings.apiToken || '';

  if (settings.connected) {
    showStatus('Connected', 'success');
    await loadProjects(settings.projectId);
  }
}

async function loadProjects(selectedProjectId) {
  try {
    const projects = await roboscope.fetchProjects();
    const select = document.getElementById('roboscope-project');
    const section = document.getElementById('roboscope-project-section');

    select.innerHTML = '<option value="">-- Select a project --</option>';
    for (const project of projects) {
      const opt = document.createElement('option');
      opt.value = project.id;
      opt.textContent = project.name || project.git_url || `Project #${project.id}`;
      if (selectedProjectId && String(project.id) === String(selectedProjectId)) {
        opt.selected = true;
      }
      select.appendChild(opt);
    }
    section.classList.remove('hidden');
  } catch {
    document.getElementById('roboscope-project-section').classList.add('hidden');
  }
}

async function saveRoboscopeSettings() {
  const serverUrl = document.getElementById('roboscope-url').value.trim();
  const apiToken = document.getElementById('roboscope-token').value.trim();

  await roboscope.saveSettings({ serverUrl, apiToken });

  if (!serverUrl || !apiToken) {
    await storage.set({ connected: false });
    document.getElementById('roboscope-project-section').classList.add('hidden');
    hideStatus();
    return;
  }

  showStatus('Saved', 'success');
}

async function testRoboscopeConnection() {
  const serverUrl = document.getElementById('roboscope-url').value.trim();
  const apiToken = document.getElementById('roboscope-token').value.trim();

  if (!serverUrl || !apiToken) {
    showStatus('Please enter both server URL and API token.', 'error');
    return;
  }

  // Save first so the client uses the latest values
  await roboscope.saveSettings({ serverUrl, apiToken });

  showStatus('Testing...', 'info');
  const result = await roboscope.testConnection();

  if (result.ok) {
    showStatus(`Connected (${result.projects.length} projects)`, 'success');
    await loadProjects();
  } else {
    showStatus(`Connection failed: ${result.error}`, 'error');
    document.getElementById('roboscope-project-section').classList.add('hidden');
  }
}

async function onProjectChange(e) {
  const projectId = e.target.value || null;
  await roboscope.setProject(projectId);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  currentLanguage = await getCurrentLanguage();

  const state = await storage.get({ locators: [] });
  document.getElementById('custom-locators').value = state.locators.join(',');

  updateUITranslations(currentLanguage);

  document.getElementById(`lang_${currentLanguage}`).checked = true;

  document.getElementById('update').addEventListener('click', update);

  Array.from(document.getElementsByClassName('language-option'))
    .forEach(elem => elem.addEventListener('change', changeLanguage));

  // RoboScope connection
  await loadRoboscopeSettings();
  document.getElementById('roboscope-save').addEventListener('click', saveRoboscopeSettings);
  document.getElementById('roboscope-test').addEventListener('click', testRoboscopeConnection);
  document.getElementById('roboscope-project').addEventListener('change', onProjectChange);
});
