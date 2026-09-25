import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Environments Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should load environments page with heading', async ({ page }) => {
    await page.locator('.nav-item', { hasText: 'Paket-Manager' }).click();
    await page.waitForURL('**/environments');

    await expect(page.locator('h1', { hasText: 'Umgebungen' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show add environment button', async ({ page }) => {
    await page.goto('/environments');
    await expect(page.locator('h1', { hasText: 'Umgebungen' })).toBeVisible({ timeout: 10_000 });

    const addButton = page.getByRole('button', { name: /Neue Umgebung/ });
    await expect(addButton).toBeVisible();
  });

  test('should open and close new environment modal', async ({ page }) => {
    await page.goto('/environments');
    await expect(page.locator('h1', { hasText: 'Umgebungen' })).toBeVisible({ timeout: 10_000 });

    // Open modal
    await page.getByRole('button', { name: /Neue Umgebung/ }).click();

    // Form fields should appear
    await expect(page.getByPlaceholder('production')).toBeVisible({ timeout: 3_000 });
    // Use exact: true to avoid matching "python:3.12-slim" too
    await expect(page.getByPlaceholder('3.12', { exact: true })).toBeVisible();

    // Cancel
    await page.getByRole('button', { name: 'Abbrechen' }).click();
    await expect(page.getByPlaceholder('production')).not.toBeVisible({ timeout: 3_000 });
  });

  // V14.2 — variables CRUD in the UI. Injection into runs is covered by pytest
  // (e2e would need a real venv run).
  test('should add, edit and delete an environment variable', async ({ page }) => {
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    const name = 'vars-e2e-' + Date.now();
    // venv_mode=system: no venv build needed for this UI-only test.
    const envResp = await page.request.post('http://localhost:8000/api/v1/environments', {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { name, python_version: '3.12', venv_mode: 'system' },
    });
    expect(envResp.ok()).toBeTruthy();

    await page.goto('/environments');
    await page.locator('.card-header', { hasText: name }).click();

    // Add
    await page.getByTestId('env-var-add').click();
    await page.getByTestId('env-var-key').fill('BASE_URL');
    await page.getByTestId('env-var-value').fill('https://staging');
    await page.getByTestId('env-var-save').click();
    const row = page.getByTestId('env-var-row').filter({ hasText: 'BASE_URL' });
    await expect(row).toContainText('https://staging', { timeout: 5_000 });

    // Edit
    await row.getByTestId('env-var-edit').click();
    await page.getByTestId('env-var-value').fill('https://prod');
    await page.getByTestId('env-var-save').click();
    await expect(row).toContainText('https://prod', { timeout: 5_000 });

    // Delete (confirm prompt)
    page.once('dialog', (d) => d.accept());
    await row.getByTestId('env-var-delete').click();
    await expect(row).toHaveCount(0, { timeout: 5_000 });

    await page.request.delete(`http://localhost:8000/api/v1/environments/${(await envResp.json()).id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  });
});
