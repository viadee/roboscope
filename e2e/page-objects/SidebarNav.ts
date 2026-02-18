import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Sidebar navigation labels as defined in AppSidebar.vue.
 * These are the German labels used in the UI.
 */
export type SidebarPage =
  | 'Dashboard'
  | 'Repositories'
  | 'Explorer'
  | 'Ausführung'
  | 'Reports'
  | 'Statistiken'
  | 'Umgebungen'
  | 'Einstellungen';

/**
 * Maps sidebar labels to their expected route paths.
 */
const PAGE_PATHS: Record<SidebarPage, string> = {
  Dashboard: '/dashboard',
  Repositories: '/repos',
  Explorer: '/explorer',
  'Ausführung': '/runs',
  Reports: '/reports',
  Statistiken: '/stats',
  Umgebungen: '/environments',
  Einstellungen: '/settings',
};

/**
 * Page Object for the sidebar navigation (AppSidebar.vue).
 *
 * Selectors are derived from the .sidebar-nav containing .nav-item links,
 * each with a .nav-label span.
 */
export class SidebarNav {
  readonly page: Page;
  readonly sidebar: Locator;
  readonly navItems: Locator;

  constructor(page: Page) {
    this.page = page;
    this.sidebar = page.locator('.sidebar');
    this.navItems = page.locator('.nav-item');
  }

  /** Get a specific nav item locator by its label text. */
  getNavItem(label: SidebarPage): Locator {
    return this.page.locator('.nav-item', { hasText: label });
  }

  /**
   * Click a sidebar navigation link and wait for navigation.
   * Returns the expected path for the page.
   */
  async navigateTo(pageName: SidebarPage): Promise<string> {
    const navItem = this.getNavItem(pageName);
    await expect(navItem).toBeVisible();
    await navItem.click();
    const expectedPath = PAGE_PATHS[pageName];
    await this.page.waitForURL(`**${expectedPath}*`);
    return expectedPath;
  }

  /**
   * Return the label of the currently active nav item.
   * The active item has the CSS class `.active`.
   */
  async getActiveLink(): Promise<string | null> {
    const activeItem = this.page.locator('.nav-item.active');
    const count = await activeItem.count();
    if (count === 0) return null;

    const label = activeItem.locator('.nav-label');
    const labelCount = await label.count();
    if (labelCount === 0) return null;

    return label.textContent();
  }

  /** Return all visible navigation labels. */
  async getAllLabels(): Promise<string[]> {
    const labels = this.page.locator('.nav-item .nav-label');
    return labels.allTextContents();
  }

  /** Assert the sidebar is visible. */
  async isVisible(): Promise<boolean> {
    await expect(this.sidebar).toBeVisible();
    return true;
  }
}
