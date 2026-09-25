import { test, expect, type Page } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const API = 'http://localhost:8000/api/v1';

async function token(page: Page): Promise<string> {
  return page.evaluate(() => localStorage.getItem('access_token') || '');
}

async function deleteEnvByName(page: Page, name: string): Promise<void> {
  const headers = { Authorization: `Bearer ${await token(page)}` };
  const envs = await (await page.request.get(`${API}/environments`, { headers })).json();
  for (const env of envs.filter((e: { name: string }) => e.name === name)) {
    await page.request.delete(`${API}/environments/${env.id}`, { headers });
  }
}

test.describe('Environments — Python source', () => {
  const name = `e2e-own-python-${Date.now()}`;

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test.afterEach(async ({ page }) => {
    await deleteEnvByName(page, name);
  });

  test('creates an environment on RoboScope\'s own Python and keeps it on delete', async ({ page }) => {
    await page.goto('/environments');
    await expect(page.locator('h1', { hasText: 'Umgebungen' })).toBeVisible({ timeout: 10_000 });

    await page.getByRole('button', { name: /Neue Umgebung/ }).click();
    await page.getByPlaceholder('production').fill(name);

    // Managed mode shows the Python version input; the own-interpreter mode hides it.
    await expect(page.getByPlaceholder('3.12', { exact: true })).toBeVisible();
    await page.getByTestId('env-venv-mode').selectOption('system');
    await expect(page.getByPlaceholder('3.12', { exact: true })).toHaveCount(0);

    // Import mode asks for a path.
    await page.getByTestId('env-venv-mode').selectOption('existing');
    await expect(page.getByTestId('env-venv-path')).toBeVisible();
    await page.getByTestId('env-venv-mode').selectOption('system');

    await page.getByRole('button', { name: 'Erstellen' }).click();

    const card = page.locator('.card', { hasText: name });
    await expect(card).toBeVisible({ timeout: 10_000 });
    await expect(card.getByTestId('env-kind-system')).toBeVisible();

    await card.locator('.card-header').click();
    await expect(card.getByTestId('env-system-notice')).toBeVisible();

    // API: the environment points at an unmanaged interpreter.
    const headers = { Authorization: `Bearer ${await token(page)}` };
    const envs = await (await page.request.get(`${API}/environments`, { headers })).json();
    const env = envs.find((e: { name: string }) => e.name === name);
    expect(env.venv_kind).toBe('system');

    // Uninstalling from RoboScope's own interpreter is refused.
    const res = await page.request.delete(`${API}/environments/${env.id}/packages/robotframework`, { headers });
    expect(res.status()).toBe(409);
  });
});
