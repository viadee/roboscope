import { test, expect, type Route } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('AI rf-mcp Knowledge Integration', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('rf-knowledge status endpoint returns availability', async ({ page }) => {
    // Mock the rf-knowledge status endpoint
    await page.route('**/api/v1/ai/rf-knowledge/status', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ available: true, url: 'http://localhost:9090/mcp' }),
      });
    });

    const response = await page.request.get('http://localhost:8000/api/v1/ai/rf-knowledge/status', {
      headers: {
        Authorization: `Bearer ${await page.evaluate(() => localStorage.getItem('access_token'))}`,
      },
    });

    // The actual endpoint returns the real status (unavailable in test env)
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('available');
    expect(data).toHaveProperty('url');
  });

  test('keyword search returns results via mocked API', async ({ page }) => {
    await page.route('**/api/v1/ai/rf-knowledge/keywords*', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            { name: 'Click Element', library: 'SeleniumLibrary', doc: 'Clicks an element.' },
            { name: 'Click Button', library: 'SeleniumLibrary', doc: 'Clicks a button element.' },
          ],
        }),
      });
    });

    const response = await page.evaluate(async () => {
      const token = localStorage.getItem('access_token');
      const resp = await fetch('/api/v1/ai/rf-knowledge/keywords?q=click', {
        headers: { Authorization: `Bearer ${token}` },
      });
      return resp.json();
    });

    expect(response.results).toHaveLength(2);
    expect(response.results[0].name).toBe('Click Element');
  });

  test('library recommend returns suggestions via mocked API', async ({ page }) => {
    await page.route('**/api/v1/ai/rf-knowledge/recommend', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          libraries: ['SeleniumLibrary', 'Browser', 'RequestsLibrary'],
        }),
      });
    });

    const response = await page.evaluate(async () => {
      const token = localStorage.getItem('access_token');
      const resp = await fetch('/api/v1/ai/rf-knowledge/recommend', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ description: 'web testing with browser automation' }),
      });
      return resp.json();
    });

    expect(response.libraries).toHaveLength(3);
    expect(response.libraries).toContain('SeleniumLibrary');
  });
});
