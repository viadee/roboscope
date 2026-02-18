import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Sidebar Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.locator('h1', { hasText: 'Dashboard' })).toBeVisible({ timeout: 10_000 });
  });

  /**
   * Core navigation items visible to all authenticated users.
   * Label = text in the sidebar nav-label.
   * Heading = the h1 rendered on the target page.
   * Path = URL path segment.
   */
  const corePages = [
    { label: 'Dashboard', heading: 'Dashboard', path: '/dashboard' },
    { label: 'Repositories', heading: 'Repositories', path: '/repos' },
    { label: 'Explorer', heading: 'Explorer', path: '/explorer' },
    { label: 'Ausführung', heading: 'Ausführung', path: '/runs' },
    { label: 'Statistiken', heading: 'Statistiken', path: '/stats' },
  ];

  for (const { label, heading, path } of corePages) {
    test(`should navigate to ${label} page via sidebar`, async ({ page }) => {
      // Click the sidebar nav item by its label text
      const navItem = page.locator('.nav-item', { hasText: label });
      await navItem.click();

      // Verify URL
      await page.waitForURL(`**${path}`, { timeout: 5_000 });
      expect(page.url()).toContain(path);

      // Verify page heading
      await expect(page.locator('h1', { hasText: heading })).toBeVisible({ timeout: 10_000 });
    });
  }

  test('should highlight the active navigation link', async ({ page }) => {
    // On dashboard, Dashboard link should be active
    const dashboardLink = page.locator('.nav-item.active');
    await expect(dashboardLink).toBeVisible();
    await expect(dashboardLink.locator('.nav-label')).toHaveText('Dashboard');

    // Navigate to Repositories
    await page.locator('.nav-item', { hasText: 'Repositories' }).click();
    await page.waitForURL('**/repos');

    // Now Repositories should be the active link
    const activeLink = page.locator('.nav-item.active');
    await expect(activeLink.locator('.nav-label')).toHaveText('Repositories');
  });

  test('should show admin-only nav items for admin user', async ({ page }) => {
    // Admin user should see Umgebungen and Einstellungen
    const allLabels = page.locator('.nav-label');
    const labels = await allLabels.allTextContents();

    expect(labels).toContain('Umgebungen');
    expect(labels).toContain('Einstellungen');
  });

  test('should navigate to Umgebungen (admin only)', async ({ page }) => {
    const navItem = page.locator('.nav-item', { hasText: 'Umgebungen' });
    await navItem.click();
    await page.waitForURL('**/environments', { timeout: 5_000 });
    await expect(page.locator('h1', { hasText: 'Umgebungen' })).toBeVisible({ timeout: 10_000 });
  });

  test('should navigate to Einstellungen (admin only)', async ({ page }) => {
    const navItem = page.locator('.nav-item', { hasText: 'Einstellungen' });
    await navItem.click();
    await page.waitForURL('**/settings', { timeout: 5_000 });
    await expect(page.locator('h1', { hasText: 'Einstellungen' })).toBeVisible({ timeout: 10_000 });
  });

  test('should display user info in sidebar footer', async ({ page }) => {
    await expect(page.locator('.user-name')).toHaveText('admin');
    await expect(page.locator('.user-role')).toHaveText('admin');
  });

  test('should display logo in sidebar header', async ({ page }) => {
    await expect(page.locator('.logo-text')).toBeVisible();
    await expect(page.locator('.logo-x')).toHaveText('X');
  });
});
