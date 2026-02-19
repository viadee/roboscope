import { test, expect } from '@playwright/test'
import { loginAndGoToDashboard } from '../helpers'

test.describe('Scheduling UX', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page)
  })

  test('shows Runs and Schedules tabs on execution page', async ({ page }) => {
    await page.goto('/execution')
    await expect(page.locator('.tab-btn', { hasText: /Runs|Ausführungen|Exécutions|Ejecuciones/ })).toBeVisible()
    await expect(page.locator('.tab-btn', { hasText: /Schedules|Zeitpläne|Planifications|Programaciones/ })).toBeVisible()
  })

  test('switches between Runs and Schedules tabs', async ({ page }) => {
    await page.goto('/execution')

    // Runs tab is active by default
    const runsTab = page.locator('.tab-btn', { hasText: /Runs|Ausführungen|Exécutions|Ejecuciones/ })
    await expect(runsTab).toHaveClass(/active/)

    // Click Schedules tab
    const schedulesTab = page.locator('.tab-btn', { hasText: /Schedules|Zeitpläne|Planifications|Programaciones/ })
    await schedulesTab.click()
    await expect(schedulesTab).toHaveClass(/active/)
  })

  test('shows empty state on schedules tab', async ({ page }) => {
    // Mock empty schedules
    await page.route('**/api/v1/schedules', route => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        })
      }
      return route.continue()
    })

    await page.goto('/execution')
    await page.locator('.tab-btn', { hasText: /Schedules|Zeitpläne|Planifications|Programaciones/ }).click()
    await expect(page.locator('.text-muted.text-center')).toBeVisible()
  })

  test('displays schedules in table', async ({ page }) => {
    await page.route('**/api/v1/schedules', route => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 1,
              name: 'Nightly Tests',
              cron_expression: '0 2 * * *',
              repository_id: 1,
              environment_id: null,
              target_path: 'tests/',
              branch: 'main',
              runner_type: 'subprocess',
              is_active: true,
              last_run_at: null,
              next_run_at: null,
              created_by: 1,
              created_at: '2026-02-15T10:00:00',
            },
            {
              id: 2,
              name: 'Weekly Smoke',
              cron_expression: '0 8 * * 1',
              repository_id: 1,
              environment_id: null,
              target_path: 'tests/smoke/',
              branch: 'main',
              runner_type: 'subprocess',
              is_active: false,
              last_run_at: null,
              next_run_at: null,
              created_by: 1,
              created_at: '2026-02-16T10:00:00',
            },
          ]),
        })
      }
      return route.continue()
    })

    await page.goto('/execution')
    await page.locator('.tab-btn', { hasText: /Schedules|Zeitpläne|Planifications|Programaciones/ }).click()

    await expect(page.locator('td', { hasText: 'Nightly Tests' })).toBeVisible({ timeout: 5_000 })
    await expect(page.locator('td', { hasText: 'Weekly Smoke' })).toBeVisible()
    await expect(page.locator('.cron-code', { hasText: '0 2 * * *' })).toBeVisible()
  })

  test('opens schedule creation dialog with cron editor', async ({ page }) => {
    await page.route('**/api/v1/schedules', route => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        })
      }
      return route.continue()
    })

    await page.goto('/execution')
    await page.locator('.tab-btn', { hasText: /Schedules|Zeitpläne|Planifications|Programaciones/ }).click()

    // Click add schedule button
    await page.locator('button', { hasText: /New Schedule|Neuer Zeitplan|Nouvelle planification|Nueva programación/ }).click()

    // Should show the cron editor with preset buttons
    await expect(page.locator('.cron-editor')).toBeVisible({ timeout: 3_000 })
    await expect(page.locator('.cron-presets')).toBeVisible()
    await expect(page.locator('.cron-fields')).toBeVisible()
    await expect(page.locator('.cron-preview')).toBeVisible()
  })

  test('cron editor presets update expression', async ({ page }) => {
    await page.route('**/api/v1/schedules', route => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        })
      }
      return route.continue()
    })

    await page.goto('/execution')
    await page.locator('.tab-btn', { hasText: /Schedules|Zeitpläne|Planifications|Programaciones/ }).click()
    await page.locator('button', { hasText: /New Schedule|Neuer Zeitplan|Nouvelle planification|Nueva programación/ }).click()

    // Click the "Hourly" preset
    await page.locator('.preset-btn', { hasText: /Hourly|Stündlich|Horaire|Horario/ }).click()

    // Should show the hourly cron expression
    await expect(page.locator('.cron-raw')).toContainText('0 * * * *')
  })
})
