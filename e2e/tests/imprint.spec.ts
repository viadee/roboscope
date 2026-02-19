import { test, expect } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('Imprint Page & Footer', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('should show footer with viadee copyright', async ({ page }) => {
    const footer = page.locator('.app-footer');
    await expect(footer).toBeVisible();
    await expect(footer).toContainText('viadee');
    await expect(footer).toContainText(new Date().getFullYear().toString());
  });

  test('should show mateo-automation link in footer', async ({ page }) => {
    const link = page.locator('.app-footer a[href*="mateo-automation"]');
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute('target', '_blank');
  });

  test('should have imprint link in footer', async ({ page }) => {
    const imprintLink = page.locator('.app-footer a[href="/imprint"]');
    await expect(imprintLink).toBeVisible();
  });

  test('should navigate to imprint page from footer', async ({ page }) => {
    await page.locator('.app-footer a[href="/imprint"]').click();
    await page.waitForURL('**/imprint');

    // Imprint page should show viadee company info
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.getByText('viadee Unternehmensberatung AG', { exact: true })).toBeVisible();
    await expect(page.getByText('Anton-Bruchausen')).toBeVisible();
    await expect(page.getByText('48147')).toBeVisible();
  });

  test('should show contact information on imprint page', async ({ page }) => {
    await page.goto('/imprint');
    await page.waitForLoadState('networkidle');

    // Contact details
    await expect(page.getByText('+49 251 777770')).toBeVisible();
    await expect(page.getByText('kontakt@viadee.de')).toBeVisible();
  });

  test('should show registration details on imprint page', async ({ page }) => {
    await page.goto('/imprint');
    await page.waitForLoadState('networkidle');

    // Registration info
    await expect(page.getByText('HRB 17380')).toBeVisible();
    await expect(page.getByText('DE170173068')).toBeVisible();
  });

  test('should show board members on imprint page', async ({ page }) => {
    await page.goto('/imprint');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('Dr. Volker Oshege')).toBeVisible();
    await expect(page.getByText('Rita Helter')).toBeVisible();
  });

  test('should show product link on imprint page', async ({ page }) => {
    await page.goto('/imprint');
    await page.waitForLoadState('networkidle');

    const productLink = page.locator('a[href="https://www.mateo-automation.com"]').first();
    await expect(productLink).toBeVisible();
  });
});
