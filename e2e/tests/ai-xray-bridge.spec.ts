import { test, expect, type Route } from '@playwright/test';
import { loginAndGoToDashboard } from '../helpers';

test.describe('AI Xray Bridge', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('export .roboscope to Xray JSON', async ({ page }) => {
    const specContent = `
version: "2"
metadata:
  title: Login Tests
  target_file: tests/login.robot
  external_id: PROJ-100
  libraries:
    - SeleniumLibrary
test_sets:
  - name: Auth Tests
    tags: [smoke]
    external_id: PROJ-50
    preconditions:
      - System is running
    test_cases:
      - name: Valid Login
        priority: high
        external_id: PROJ-101
        preconditions:
          - User is on login page
        steps:
          - Navigate to login page
          - action: Enter credentials
            data: "user: admin, pass: secret"
            expected_result: Fields are filled
`;

    const response = await page.evaluate(async (content) => {
      const token = localStorage.getItem('access_token');
      const resp = await fetch('/api/v1/ai/xray/export', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      });
      return resp.json();
    }, specContent);

    expect(response).toHaveProperty('info');
    expect(response).toHaveProperty('tests');
    expect(response.info.testPlanKey).toBe('PROJ-100');
    expect(response.tests).toHaveLength(1);
    expect(response.tests[0].testKey).toBe('PROJ-101');
    expect(response.tests[0].testInfo.summary).toBe('Valid Login');
    expect(response.tests[0].testInfo.priority).toBe('High');
    expect(response.tests[0].steps).toHaveLength(2);
    expect(response.tests[0].steps[0].fields.Action).toBe('Navigate to login page');
    expect(response.tests[0].steps[1].fields.Data).toBe('user: admin, pass: secret');
  });

  test('import Xray JSON to .roboscope YAML', async ({ page }) => {
    const xrayData = {
      info: {
        summary: 'Imported Suite',
        testPlanKey: 'XRAY-500',
      },
      tests: [
        {
          testKey: 'XRAY-501',
          testInfo: {
            summary: 'Test Login',
            description: 'Verify login works',
            priority: 'High',
            labels: ['smoke'],
            precondition: 'User account exists',
          },
          steps: [
            { fields: { Action: 'Open browser' } },
            {
              fields: {
                Action: 'Enter credentials',
                Data: 'admin / secret',
                'Expected Result': 'Login successful',
              },
            },
          ],
        },
      ],
    };

    const response = await page.evaluate(async (data) => {
      const token = localStorage.getItem('access_token');
      const resp = await fetch('/api/v1/ai/xray/import', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      return resp.json();
    }, xrayData);

    expect(response).toHaveProperty('content');
    const yamlContent = response.content;

    // Verify the YAML contains expected data
    expect(yamlContent).toContain('version: \'2\'');
    expect(yamlContent).toContain('XRAY-500');
    expect(yamlContent).toContain('XRAY-501');
    expect(yamlContent).toContain('Test Login');
    expect(yamlContent).toContain('Open browser');
    expect(yamlContent).toContain('Enter credentials');
  });

  test('validate v2 spec with structured steps', async ({ page }) => {
    const content = `
version: "2"
metadata:
  title: Bridge Test
  target_file: test.robot
  external_id: BT-100
test_sets:
  - name: Test Set
    external_id: BT-50
    preconditions:
      - Environment is ready
    test_cases:
      - name: Structured Steps Test
        external_id: BT-101
        preconditions:
          - User is authenticated
        steps:
          - Simple string step
          - action: Click button
            data: button_id=submit
            expected_result: Form is submitted
`;

    const response = await page.evaluate(async (yamlContent) => {
      const token = localStorage.getItem('access_token');
      const resp = await fetch('/api/v1/ai/validate', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: yamlContent }),
      });
      return resp.json();
    }, content);

    expect(response.valid).toBe(true);
    expect(response.test_count).toBe(1);
    expect(response.errors).toHaveLength(0);
  });
});
