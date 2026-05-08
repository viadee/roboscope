/**
 * RoboScope API client for the Chrome extension.
 *
 * Communicates with the RoboScope backend recording API.
 * Falls back gracefully when no connection is configured.
 */

import logger from './logger.js';

const storage = chrome.storage.local;

/** Storage keys for RoboScope connection settings. */
const SETTINGS_KEYS = {
  serverUrl: '',       // e.g. http://localhost:8000
  apiToken: '',        // RoboScope API token (rbs_xxx or JWT)
  projectId: null,     // Selected project/repo ID
  connected: false,    // Connection status
};

/**
 * Get the current RoboScope connection settings.
 */
export async function getSettings() {
  return storage.get(SETTINGS_KEYS);
}

/**
 * Save RoboScope connection settings.
 */
export async function saveSettings({ serverUrl, apiToken }) {
  const clean = {
    serverUrl: (serverUrl || '').replace(/\/+$/, ''),  // strip trailing slash
    apiToken: apiToken || '',
  };
  await storage.set(clean);
  return clean;
}

/**
 * Check if RoboScope connection is configured.
 */
export async function isConfigured() {
  const { serverUrl, apiToken } = await getSettings();
  return !!(serverUrl && apiToken);
}

/**
 * Make an authenticated API request to RoboScope.
 */
async function apiRequest(method, path, body = null) {
  const { serverUrl, apiToken } = await getSettings();
  if (!serverUrl || !apiToken) {
    throw new Error('RoboScope not configured');
  }

  const url = `${serverUrl}/api/v1${path}`;
  const headers = {
    'Authorization': `Bearer ${apiToken}`,
    'Content-Type': 'application/json',
  };

  const opts = { method, headers };
  if (body) {
    opts.body = JSON.stringify(body);
  }

  const response = await fetch(url, opts);

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`RoboScope API ${response.status}: ${text}`);
  }

  if (response.status === 204) return null;
  return response.json();
}

// ---------------------------------------------------------------------------
// Connection test
// ---------------------------------------------------------------------------

/**
 * Test the connection to RoboScope and fetch available projects.
 * Returns { ok, projects, error }.
 */
export async function testConnection() {
  try {
    const projects = await apiRequest('GET', '/repos');
    await storage.set({ connected: true });
    return { ok: true, projects };
  } catch (err) {
    await storage.set({ connected: false });
    return { ok: false, projects: [], error: err.message };
  }
}

// ---------------------------------------------------------------------------
// Recording API
// ---------------------------------------------------------------------------

/**
 * Create a new recording session on RoboScope.
 */
export async function createRecording({ projectId, targetUrl, targetLibrary = 'Browser' }) {
  return apiRequest('POST', '/recordings', {
    repository_id: projectId,
    source: 'extension',
    target_url: targetUrl,
    target_library: targetLibrary,
  });
}

/**
 * Start a recording session.
 */
export async function startRecording(recordingId) {
  return apiRequest('POST', `/recordings/${recordingId}/start`);
}

/**
 * Send a recorded event to RoboScope.
 */
export async function sendEvent(recordingId, event) {
  return apiRequest('POST', `/recordings/${recordingId}/event`, event);
}

/**
 * Stop a recording session and trigger .robot generation.
 */
export async function stopRecording(recordingId, { generateRobot = true } = {}) {
  return apiRequest('POST', `/recordings/${recordingId}/stop`, {
    generate_robot: generateRobot,
  });
}

/**
 * Cancel a recording session.
 */
export async function cancelRecording(recordingId) {
  return apiRequest('POST', `/recordings/${recordingId}/cancel`);
}

/**
 * Get the generated .robot file content.
 */
export async function getGeneratedRobot(recordingId) {
  const { serverUrl, apiToken } = await getSettings();
  const url = `${serverUrl}/api/v1/recordings/${recordingId}/robot`;
  const response = await fetch(url, {
    headers: { 'Authorization': `Bearer ${apiToken}` },
  });
  if (!response.ok) throw new Error(`Failed to fetch robot: ${response.status}`);
  return response.text();
}

/**
 * Fetch available projects from RoboScope.
 */
export async function fetchProjects() {
  return apiRequest('GET', '/repos');
}

/**
 * Set the selected project ID.
 */
export async function setProject(projectId) {
  await storage.set({ projectId });
}

/**
 * Get the currently selected project ID.
 */
export async function getProjectId() {
  const { projectId } = await storage.get({ projectId: null });
  return projectId;
}
