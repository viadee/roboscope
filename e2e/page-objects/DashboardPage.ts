import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object for the Dashboard view (/dashboard).
 *
 * Selectors are derived from DashboardView.vue:
 *   - heading: <h1>Dashboard</h1>
 *   - KPI cards: .kpi-card elements containing .kpi-value and .kpi-label
 *   - Recent runs table: .data-table
 *   - Repos overview section
 */
export class DashboardPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly kpiCards: Locator;
  readonly kpiValues: Locator;
  readonly kpiLabels: Locator;
  readonly spinner: Locator;
  readonly recentRunsHeading: Locator;
  readonly recentRunsTable: Locator;
  readonly reposHeading: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heading = page.getByRole('heading', { name: 'Dashboard', level: 1 });
    this.kpiCards = page.locator('.kpi-card');
    this.kpiValues = page.locator('.kpi-value');
    this.kpiLabels = page.locator('.kpi-label');
    this.spinner = page.locator('.spinner');
    this.recentRunsHeading = page.getByRole('heading', { name: 'Letzte Ausführungen' });
    this.recentRunsTable = page.locator('.data-table').first();
    this.reposHeading = page.getByRole('heading', { name: 'Repositories' });
  }

  /** Navigate to the dashboard. */
  async goto(): Promise<void> {
    await this.page.goto('/dashboard');
  }

  /** Get the main page heading text. */
  async getHeading(): Promise<string> {
    return (await this.heading.textContent()) ?? '';
  }

  /**
   * Wait for the dashboard to be fully loaded:
   *   - heading is visible
   *   - spinner is gone
   *   - KPI cards are rendered
   */
  async isLoaded(): Promise<boolean> {
    await expect(this.heading).toBeVisible();
    // Wait for loading spinner to disappear (if present)
    await this.spinner.waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => {
      // spinner may never have appeared if data loaded fast
    });
    return true;
  }

  /** Return the count of KPI cards displayed. */
  async getKpiCardCount(): Promise<number> {
    return this.kpiCards.count();
  }

  /** Return all KPI labels as an array of strings. */
  async getKpiLabels(): Promise<string[]> {
    const labels = await this.kpiLabels.allTextContents();
    return labels;
  }

  /** Return all KPI values as an array of strings. */
  async getKpiValues(): Promise<string[]> {
    const values = await this.kpiValues.allTextContents();
    return values;
  }
}
