import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

const MOBILE_VIEWPORT = { width: 375, height: 812 };
const TABLET_VIEWPORT = { width: 768, height: 1024 };
const DESKTOP_VIEWPORT = { width: 1280, height: 800 };

test.describe('Responsive Design — Mobile', () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });
  });

  test('sidebar is hidden by default on mobile', async ({ page }) => {
    const sidebar = page.locator('.sidebar');
    // Sidebar should be off-screen (translated left)
    await expect(sidebar).toHaveCSS('transform', /translateX/);
  });

  test('hamburger menu opens sidebar as overlay', async ({ page }) => {
    // Click hamburger toggle
    const toggleBtn = page.locator('.toggle-btn');
    await toggleBtn.click();

    // Sidebar should now be visible
    const sidebar = page.locator('.sidebar');
    await expect(sidebar).toBeVisible();

    // Backdrop should be visible
    const backdrop = page.locator('.sidebar-backdrop');
    await expect(backdrop).toBeVisible();
  });

  test('clicking backdrop closes sidebar on mobile', async ({ page }) => {
    // Open sidebar
    await page.locator('.toggle-btn').click();
    await expect(page.locator('.sidebar-backdrop')).toBeVisible();

    // Click backdrop to close
    await page.locator('.sidebar-backdrop').click();

    // Backdrop should disappear
    await expect(page.locator('.sidebar-backdrop')).not.toBeVisible();
  });

  test('sidebar closes after navigation on mobile', async ({ page }) => {
    // Open sidebar
    await page.locator('.toggle-btn').click();
    await expect(page.locator('.sidebar-backdrop')).toBeVisible();

    // Click a nav item
    const statsNav = page.locator('.nav-item', { hasText: 'Statistiken' });
    await statsNav.click();

    // Sidebar should close (backdrop gone)
    await expect(page.locator('.sidebar-backdrop')).not.toBeVisible({ timeout: 3_000 });
  });

  test('main content takes full width on mobile', async ({ page }) => {
    const mainArea = page.locator('.main-area');
    // On mobile, margin-left should be 0 (not 250px or 60px)
    await expect(mainArea).toHaveCSS('margin-left', '0px');
  });

  test('username is hidden in header on mobile', async ({ page }) => {
    const headerUser = page.locator('.header-user');
    await expect(headerUser).not.toBeVisible();
  });

  test('KPI grid collapses to single column on mobile', async ({ page }) => {
    const kpiGrid = page.locator('.grid.grid-4');
    if (await kpiGrid.count() > 0) {
      const gridStyle = await kpiGrid.evaluate(el => getComputedStyle(el).gridTemplateColumns);
      // Should be a single column on mobile
      const columns = gridStyle.split(' ').filter(v => v !== '');
      expect(columns.length).toBe(1);
    }
  });

  test('page header stacks vertically on mobile', async ({ page }) => {
    const pageHeader = page.locator('.page-header');
    const flexDirection = await pageHeader.evaluate(el => getComputedStyle(el).flexDirection);
    expect(flexDirection).toBe('column');
  });

  test('data tables are horizontally scrollable', async ({ page }) => {
    const tableWrapper = page.locator('.table-responsive').first();
    if (await tableWrapper.count() > 0) {
      const overflowX = await tableWrapper.evaluate(el => getComputedStyle(el).overflowX);
      expect(overflowX).toBe('auto');
    }
  });
});

test.describe('Responsive Design — Tablet', () => {
  test.use({ viewport: TABLET_VIEWPORT });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });
  });

  test('KPI grid shows 2 columns on tablet', async ({ page }) => {
    const kpiGrid = page.locator('.grid.grid-4');
    if (await kpiGrid.count() > 0) {
      const gridStyle = await kpiGrid.evaluate(el => getComputedStyle(el).gridTemplateColumns);
      const columns = gridStyle.split(' ').filter(v => v !== '');
      // At 768px, grid-4 should have 2 columns (1024px breakpoint)
      expect(columns.length).toBe(2);
    }
  });
});

test.describe('Responsive Design — Desktop', () => {
  test.use({ viewport: DESKTOP_VIEWPORT });

  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 });
  });

  test('sidebar is visible on desktop', async ({ page }) => {
    const sidebar = page.locator('.sidebar');
    await expect(sidebar).toBeVisible();
    // No backdrop on desktop
    await expect(page.locator('.sidebar-backdrop')).not.toBeVisible();
  });

  test('main content has sidebar margin on desktop', async ({ page }) => {
    const mainArea = page.locator('.main-area');
    const marginLeft = await mainArea.evaluate(el => getComputedStyle(el).marginLeft);
    expect(parseInt(marginLeft)).toBe(250);
  });

  test('username is visible in header on desktop', async ({ page }) => {
    const headerUser = page.locator('.header-user');
    await expect(headerUser).toBeVisible();
  });

  test('KPI grid shows 4 columns on desktop', async ({ page }) => {
    const kpiGrid = page.locator('.grid.grid-4');
    if (await kpiGrid.count() > 0) {
      const gridStyle = await kpiGrid.evaluate(el => getComputedStyle(el).gridTemplateColumns);
      const columns = gridStyle.split(' ').filter(v => v !== '');
      expect(columns.length).toBe(4);
    }
  });

  test('sidebar toggle collapses to icon-only mode', async ({ page }) => {
    await page.locator('.toggle-btn').click();

    // Main area should now have 60px margin
    const mainArea = page.locator('.main-area');
    const marginLeft = await mainArea.evaluate(el => getComputedStyle(el).marginLeft);
    expect(parseInt(marginLeft)).toBe(60);

    // Nav labels should be hidden
    await expect(page.locator('.nav-label').first()).not.toBeVisible();
  });
});
