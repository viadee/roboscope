import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Library Check Feature', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should show Library Check button on repo cards', async ({ page }) => {
    // Mock repos API to return a repo
    await page.route('**/api/v1/repos', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 1,
              name: 'test-repo',
              repo_type: 'local',
              git_url: null,
              default_branch: 'main',
              local_path: '/tmp/test',
              last_synced_at: null,
              auto_sync: false,
              sync_interval_minutes: 15,
              sync_status: 'idle',
              sync_error: null,
              created_by: 1,
              environment_id: null,
              created_at: '2024-01-01T00:00:00',
              updated_at: '2024-01-01T00:00:00',
            },
          ]),
        });
      } else {
        await route.continue();
      }
    });

    // Mock environments API
    await page.route('**/api/v1/environments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 1,
            name: 'default-env',
            python_version: '3.12',
            venv_path: '/tmp/venv',
            docker_image: null,
            is_default: true,
            description: null,
            created_by: 1,
            created_at: '2024-01-01T00:00:00',
            updated_at: '2024-01-01T00:00:00',
          },
        ]),
      });
    });

    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });

    // Library Check button should be visible
    const libCheckButton = page.getByRole('button', { name: /Library.Check/i });
    await expect(libCheckButton).toBeVisible();
  });

  test('should open Library Check modal and scan', async ({ page }) => {
    // Mock repos
    await page.route('**/api/v1/repos', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 1,
              name: 'test-repo',
              repo_type: 'local',
              git_url: null,
              default_branch: 'main',
              local_path: '/tmp/test',
              last_synced_at: null,
              auto_sync: false,
              sync_interval_minutes: 15,
              sync_status: 'idle',
              sync_error: null,
              created_by: 1,
              environment_id: 1,
              created_at: '2024-01-01T00:00:00',
              updated_at: '2024-01-01T00:00:00',
            },
          ]),
        });
      } else {
        await route.continue();
      }
    });

    // Mock environments
    await page.route('**/api/v1/environments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 1,
            name: 'default-env',
            python_version: '3.12',
            venv_path: '/tmp/venv',
            docker_image: null,
            is_default: true,
            description: null,
            created_by: 1,
            created_at: '2024-01-01T00:00:00',
            updated_at: '2024-01-01T00:00:00',
          },
        ]),
      });
    });

    // Mock library-check endpoint
    await page.route('**/api/v1/explorer/1/library-check*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          repo_id: 1,
          environment_id: 1,
          environment_name: 'default-env',
          total_libraries: 3,
          missing_count: 1,
          installed_count: 1,
          builtin_count: 1,
          libraries: [
            {
              library_name: 'Browser',
              pypi_package: 'robotframework-browser',
              status: 'installed',
              installed_version: '18.0.0',
              files: ['tests/login.robot'],
            },
            {
              library_name: 'SeleniumLibrary',
              pypi_package: 'robotframework-seleniumlibrary',
              status: 'missing',
              installed_version: null,
              files: ['tests/ui.robot'],
            },
            {
              library_name: 'Collections',
              pypi_package: null,
              status: 'builtin',
              installed_version: null,
              files: ['tests/utils.robot'],
            },
          ],
        }),
      });
    });

    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });

    // Click Library Check button
    await page.getByRole('button', { name: /Library.Check/i }).click();

    // Modal should open (title is "Library-Check" with hyphen)
    await expect(page.getByRole('heading', { name: 'Library-Check' })).toBeVisible({ timeout: 5_000 });

    // Environment dropdown should be visible
    const envSelect = page.locator('select');
    await expect(envSelect.first()).toBeVisible();

    // Click Scan button
    await page.getByRole('button', { name: /Scan/i }).click();

    // Results should appear (use exact to avoid matching pypi package names)
    await expect(page.getByText('Browser', { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('SeleniumLibrary', { exact: true })).toBeVisible();
    await expect(page.getByText('Collections', { exact: true })).toBeVisible();

    // Status badges should be visible (German UI: Installiert, Fehlt, Built-in)
    await expect(page.locator('.lib-check-status', { hasText: /Installiert|Installed/i })).toBeVisible();
    await expect(page.locator('.lib-check-status', { hasText: /Fehlt|Missing/i })).toBeVisible();
    await expect(page.locator('.lib-check-status', { hasText: /Built-in/i })).toBeVisible();

    // Install button should appear for missing library (German: "Installieren")
    const installButtons = page.getByRole('button', { name: /Install/i });
    await expect(installButtons.first()).toBeVisible();

    // Summary should show (German: "3 Libraries: 1 installiert...")
    await expect(page.getByText(/3 Libraries/i)).toBeVisible();
  });

  test('should show environment dropdown in add repo dialog', async ({ page }) => {
    // Mock environments
    await page.route('**/api/v1/environments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 1,
            name: 'test-env',
            python_version: '3.12',
            venv_path: '/tmp/venv',
            docker_image: null,
            is_default: false,
            description: null,
            created_by: 1,
            created_at: '2024-01-01T00:00:00',
            updated_at: '2024-01-01T00:00:00',
          },
        ]),
      });
    });

    // Mock repos
    await page.route('**/api/v1/repos', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });

    // Open add dialog
    await page.getByRole('button', { name: '+ Projekt hinzufügen' }).click();

    // Environment dropdown should be in the form
    await expect(page.getByText(/Default Environment|Standard-Umgebung/i)).toBeVisible({ timeout: 3_000 });
  });

  test('nav should show Package Manager instead of Environments', async ({ page }) => {
    await page.goto('/environments');
    await page.waitForLoadState('networkidle');

    // The nav item should now say "Package Manager" (or the translated equivalent)
    const navItem = page.locator('.nav-item', { hasText: /Package Manager|Paket-Manager/i });
    await expect(navItem).toBeVisible({ timeout: 10_000 });
  });
});
