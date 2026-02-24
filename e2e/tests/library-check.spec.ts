import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

// Shared mock data for reuse across tests
const repoMock = {
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
};

const envMock = {
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
};

const dockerEnvironment = {
  ...envMock,
  docker_image: 'roboscope/test:latest',
};

const baseLibCheckResponse = {
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
};

const dockerLibCheckResponse = {
  ...baseLibCheckResponse,
  docker_image: 'roboscope/test:latest',
  docker_missing_count: 1,
  libraries: [
    {
      library_name: 'Browser',
      pypi_package: 'robotframework-browser',
      status: 'installed',
      installed_version: '18.0.0',
      docker_status: 'installed',
      docker_installed_version: '17.5.0',
      files: ['tests/login.robot'],
    },
    {
      library_name: 'SeleniumLibrary',
      pypi_package: 'robotframework-seleniumlibrary',
      status: 'missing',
      installed_version: null,
      docker_status: 'missing',
      docker_installed_version: null,
      files: ['tests/ui.robot'],
    },
    {
      library_name: 'Collections',
      pypi_package: null,
      status: 'builtin',
      installed_version: null,
      docker_status: null,
      docker_installed_version: null,
      files: ['tests/utils.robot'],
    },
  ],
};

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
          body: JSON.stringify([{ ...repoMock, environment_id: null }]),
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
        body: JSON.stringify([envMock]),
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
          body: JSON.stringify([repoMock]),
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
        body: JSON.stringify([envMock]),
      });
    });

    // Mock library-check endpoint
    await page.route('**/api/v1/explorer/1/library-check*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(baseLibCheckResponse),
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
        body: JSON.stringify([{ ...envMock, name: 'test-env', is_default: false }]),
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

  test('should show Docker column when docker_image is set', async ({ page }) => {
    // Mock repos with environment_id
    await page.route('**/api/v1/repos', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([repoMock]),
        });
      } else {
        await route.continue();
      }
    });

    // Mock Docker-enabled environment
    await page.route('**/api/v1/environments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([dockerEnvironment]),
      });
    });

    // Mock library-check with Docker fields
    await page.route('**/api/v1/explorer/1/library-check*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(dockerLibCheckResponse),
      });
    });

    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });

    // Click Library Check button and scan
    await page.getByRole('button', { name: /Library.Check/i }).click();
    await expect(page.getByRole('heading', { name: 'Library-Check' })).toBeVisible({ timeout: 5_000 });
    await page.getByRole('button', { name: /Scan/i }).click();

    // Docker column header should be visible
    await expect(page.locator('th', { hasText: /Docker/i })).toBeVisible({ timeout: 5_000 });

    // Docker status badges should be visible (installed/missing)
    const dockerCells = page.locator('td').filter({ hasText: /Installiert|Installed|Fehlt|Missing/i });
    await expect(dockerCells.first()).toBeVisible();

    // Rebuild Docker Image button should be visible
    const rebuildBtn = page.getByRole('button', { name: /Rebuild Docker|Docker.Image neu bauen/i });
    await expect(rebuildBtn).toBeVisible();

    // Summary should contain Docker missing count
    await expect(page.locator('.lib-check-summary', { hasText: /Docker/i })).toBeVisible();
  });

  test('should NOT show Docker column when no docker_image', async ({ page }) => {
    // Mock repos
    await page.route('**/api/v1/repos', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([repoMock]),
        });
      } else {
        await route.continue();
      }
    });

    // Mock environment WITHOUT docker_image
    await page.route('**/api/v1/environments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([envMock]),
      });
    });

    // Mock library-check WITHOUT Docker fields
    await page.route('**/api/v1/explorer/1/library-check*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...baseLibCheckResponse, docker_image: null }),
      });
    });

    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });

    // Click Library Check and scan
    await page.getByRole('button', { name: /Library.Check/i }).click();
    await expect(page.getByRole('heading', { name: 'Library-Check' })).toBeVisible({ timeout: 5_000 });
    await page.getByRole('button', { name: /Scan/i }).click();

    // Wait for results to load
    await expect(page.getByText('Browser', { exact: true })).toBeVisible({ timeout: 5_000 });

    // No Docker column header
    await expect(page.locator('th', { hasText: /Docker/i })).not.toBeVisible();

    // No Rebuild Docker button
    await expect(page.getByRole('button', { name: /Rebuild Docker|Docker.Image neu bauen/i })).not.toBeVisible();
  });

  test('should trigger docker-build API when clicking Rebuild button', async ({ page }) => {
    let dockerBuildCalled = false;

    // Mock repos
    await page.route('**/api/v1/repos', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([repoMock]),
        });
      } else {
        await route.continue();
      }
    });

    // Mock Docker-enabled environment
    await page.route('**/api/v1/environments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([dockerEnvironment]),
      });
    });

    // Mock library-check with Docker fields
    await page.route('**/api/v1/explorer/1/library-check*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(dockerLibCheckResponse),
      });
    });

    // Mock docker-build endpoint and track calls
    await page.route('**/api/v1/environments/*/docker-build', async (route) => {
      dockerBuildCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'started', image_tag: 'roboscope/test:latest' }),
      });
    });

    await page.goto('/repos');
    await expect(page.locator('h1', { hasText: 'Projekte' })).toBeVisible({ timeout: 10_000 });

    // Open Library Check, scan, then click Rebuild
    await page.getByRole('button', { name: /Library.Check/i }).click();
    await expect(page.getByRole('heading', { name: 'Library-Check' })).toBeVisible({ timeout: 5_000 });
    await page.getByRole('button', { name: /Scan/i }).click();

    // Wait for Rebuild button and click it
    const rebuildBtn = page.getByRole('button', { name: /Rebuild Docker|Docker.Image neu bauen/i });
    await expect(rebuildBtn).toBeVisible({ timeout: 5_000 });
    await rebuildBtn.click();

    // Verify docker-build API was called
    await page.waitForTimeout(500);
    expect(dockerBuildCalled).toBe(true);
  });
});
