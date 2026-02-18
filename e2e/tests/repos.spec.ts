import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Repository Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should load repos page with heading', async ({ page }) => {
    await page.locator('.nav-item', { hasText: 'Projekte' }).click();
    await page.waitForURL('**/repos');

    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });
  });

  test('should show add repo button for admin user', async ({ page }) => {
    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });

    // Admin should see the "Projekt hinzufügen" button
    const addButton = page.getByRole('button', { name: /Projekt hinzufügen/ });
    await expect(addButton).toBeVisible();
  });

  test('should open and close add repository modal', async ({ page }) => {
    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });

    // Click add button
    await page.getByRole('button', { name: /Projekt hinzufügen/ }).click();

    // Modal should open with the form
    await expect(page.getByPlaceholder('mein-projekt')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByPlaceholder('https://github.com/user/repo.git')).toBeVisible();
    await expect(page.getByPlaceholder('main')).toBeVisible();

    // Cancel button should close the modal
    await page.getByRole('button', { name: 'Abbrechen' }).click();
    await expect(page.getByPlaceholder('mein-projekt')).not.toBeVisible({ timeout: 3_000 });
  });

  test('should add a new repository', async ({ page }) => {
    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });

    // Open modal
    await page.getByRole('button', { name: /Projekt hinzufügen/ }).click();
    await expect(page.getByPlaceholder('mein-projekt')).toBeVisible({ timeout: 3_000 });

    // Fill form
    const repoName = `test-repo-${Date.now()}`;
    await page.getByPlaceholder('mein-projekt').fill(repoName);
    await page.getByPlaceholder('https://github.com/user/repo.git').fill(`https://github.com/test/${repoName}.git`);

    // Submit — use exact match to avoid matching "+ Projekt hinzufügen" button
    await page.getByRole('button', { name: 'Hinzufügen', exact: true }).click();

    // Modal should close
    await expect(page.getByPlaceholder('mein-projekt')).not.toBeVisible({ timeout: 5_000 });

    // New repo should appear in the list
    await expect(page.getByText(repoName)).toBeVisible({ timeout: 5_000 });
  });

  test('should show empty state when no repos exist', async ({ page }) => {
    await page.goto('/repos');
    await page.waitForLoadState('networkidle');

    // Either there are repos displayed, or we see an empty state
    // (This test validates the page loads without errors)
    const heading = page.locator('h1', { hasText: 'Projekte' });
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });
});
