import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object for the Login view (/login).
 *
 * Selectors are derived from the actual LoginView.vue template:
 *   - email input: placeholder "admin@mateox.local"
 *   - password input: placeholder "Passwort"
 *   - submit button: text "Anmelden"
 *   - error message: .error-text paragraph
 */
export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;
  readonly heading: Locator;
  readonly hint: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.getByPlaceholder('admin@mateox.local');
    this.passwordInput = page.getByPlaceholder('Passwort');
    this.submitButton = page.getByRole('button', { name: 'Anmelden' });
    this.errorMessage = page.locator('.error-text');
    this.heading = page.getByRole('heading', { name: 'Anmelden' });
    this.hint = page.locator('.hint');
  }

  /** Navigate to the login page. */
  async goto(): Promise<void> {
    await this.page.goto('/login');
  }

  /** Fill in credentials and submit the login form. */
  async login(email: string, password: string): Promise<void> {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  /** Return the visible error message text, or null if no error is shown. */
  async getErrorMessage(): Promise<string | null> {
    const isVisible = await this.errorMessage.isVisible();
    if (!isVisible) return null;
    return this.errorMessage.textContent();
  }

  /** Assert that the login page is fully visible. */
  async isVisible(): Promise<boolean> {
    await expect(this.heading).toBeVisible();
    await expect(this.emailInput).toBeVisible();
    await expect(this.passwordInput).toBeVisible();
    await expect(this.submitButton).toBeVisible();
    return true;
  }
}
