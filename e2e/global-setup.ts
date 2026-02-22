import { FullConfig, request } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const AUTH_STATE_PATH = path.join(__dirname, '.auth-state.json');

/**
 * Global setup: authenticates the default admin user via the API
 * and persists the auth state (tokens) so test fixtures can reuse it
 * without logging in for every test.
 */
async function globalSetup(_config: FullConfig): Promise<void> {
  const apiBaseURL = process.env.API_BASE_URL || 'http://localhost:8000';

  const apiContext = await request.newContext({
    baseURL: apiBaseURL,
  });

  try {
    const loginResponse = await apiContext.post('/api/v1/auth/login', {
      data: {
        email: 'admin@roboscope.local',
        password: 'admin123',
      },
    });

    if (!loginResponse.ok()) {
      console.warn(
        `[global-setup] Login failed with status ${loginResponse.status()}. ` +
        `Tests requiring authentication will attempt login individually.`
      );
      // Write an empty state so the file exists but signals "no pre-auth"
      fs.writeFileSync(AUTH_STATE_PATH, JSON.stringify({ authenticated: false }));
      return;
    }

    const tokens = await loginResponse.json();

    // Fetch the user profile using the obtained token
    const meResponse = await apiContext.get('/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${tokens.access_token}`,
      },
    });

    const user = meResponse.ok() ? await meResponse.json() : null;

    const authState = {
      authenticated: true,
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      user,
    };

    fs.writeFileSync(AUTH_STATE_PATH, JSON.stringify(authState, null, 2));
    console.log('[global-setup] Admin auth state saved successfully.');
  } finally {
    await apiContext.dispose();
  }
}

export default globalSetup;
