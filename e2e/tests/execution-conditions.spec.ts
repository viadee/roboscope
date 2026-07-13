/**
 * Execution under different start conditions.
 *
 * Covers the execution gap from the use-case audit (2026-07-02):
 *  - tags_include actually SCOPES the run (not just carried on the POST),
 *  - variables actually reach the Robot process (run fails without them,
 *    passes with them),
 *  - a directory target executes every test underneath it,
 *  - the repo tag discovery endpoint feeds the run-dialog <datalist>.
 *
 * Runs execute on the backend interpreter (no environment), like the
 * Examples-repo runs in execution-run.spec.ts.
 */
import { test, expect, type Page } from '@playwright/test';

const API = 'http://localhost:8000/api/v1';
const EMAIL = 'admin@roboscope.local';
const PASSWORD = 'admin123';

const TAGGED_ROBOT = `*** Test Cases ***
Tagged Test
    [Tags]    smoke
    Log    tagged-ran

Untagged Test
    Log    untagged-ran
`;

const VARS_ROBOT = `*** Test Cases ***
Variable Test
    Should Be Equal    ${'${GREETING}'}    from-e2e

Variable Log Test
    Log    ${'${GREETING}'}
`;

async function getAuthToken(page: Page): Promise<string> {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: EMAIL, password: PASSWORD } });
  return (await res.json()).access_token as string;
}

async function cancelAllRuns(page: Page, token: string): Promise<void> {
  await page.request.post(`${API}/runs/cancel-all`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await page.waitForTimeout(2000);
}

/** Poll a run to a terminal state (out-waits the single-worker executor queue). */
async function pollRunToCompletion(page: Page, token: string, runId: number, maxIterations = 110): Promise<any> {
  let detail: any;
  for (let i = 0; i < maxIterations; i++) {
    await page.waitForTimeout(2000);
    const res = await page.request.get(`${API}/runs/${runId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    detail = await res.json();
    if (['passed', 'failed', 'error', 'timeout', 'cancelled'].includes(detail.status)) return detail;
  }
  return detail;
}

async function startRun(page: Page, token: string, data: Record<string, unknown>): Promise<number> {
  const res = await page.request.post(`${API}/runs`, {
    headers: { Authorization: `Bearer ${token}` },
    data,
  });
  expect(res.status()).toBe(201);
  return (await res.json()).id as number;
}

async function getRunStdout(page: Page, token: string, runId: number): Promise<string> {
  const res = await page.request.get(`${API}/runs/${runId}/output`, {
    headers: { Authorization: `Bearer ${token}` },
    params: { stream: 'stdout' },
  });
  return await res.text();
}

test.describe.serial('Execution — start conditions', () => {
  let token: string;
  let repoId: number;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    token = await getAuthToken(page);
    const stamp = Date.now();
    const res = await page.request.post(`${API}/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: `exec-cond-e2e-${stamp}`, repo_type: 'local', local_path: `/tmp/roboscope-exec-cond-${stamp}` },
    });
    expect(res.status()).toBe(201);
    repoId = (await res.json()).id as number;
    for (const [path, content] of [
      ['tests/tagged/tagged.robot', TAGGED_ROBOT],
      ['tests/vars/vars.robot', VARS_ROBOT],
    ] as const) {
      const fr = await page.request.post(`${API}/explorer/${repoId}/file`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { path, content },
      });
      expect(fr.status()).toBeLessThan(300);
    }
    await page.close();
  });

  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    const t = await getAuthToken(page);
    await cancelAllRuns(page, t);
    await page.request.delete(`${API}/repos/${repoId}`, { headers: { Authorization: `Bearer ${t}` } });
    await page.close();
  });

  test('tags_include scopes the run to matching tests only', async ({ page }) => {
    test.setTimeout(300_000);
    await cancelAllRuns(page, token);

    const runId = await startRun(page, token, {
      repository_id: repoId,
      target_path: 'tests/tagged/tagged.robot',
      tags_include: 'smoke',
    });
    const detail = await pollRunToCompletion(page, token, runId);
    expect(detail.status).toBe('passed');

    const stdout = await getRunStdout(page, token, runId);
    expect(stdout).toContain('Tagged Test');
    expect(stdout).not.toContain('Untagged Test');
  });

  test('variables reach the Robot process (fail without, pass with)', async ({ page }) => {
    test.setTimeout(500_000);

    // Control: without the variable, RF cannot resolve ${GREETING} → failed
    const withoutId = await startRun(page, token, {
      repository_id: repoId,
      target_path: 'tests/vars/vars.robot',
    });
    const withoutDetail = await pollRunToCompletion(page, token, withoutId);
    expect(['failed', 'error']).toContain(withoutDetail.status);

    // With the variable the same suite passes
    const withId = await startRun(page, token, {
      repository_id: repoId,
      target_path: 'tests/vars/vars.robot',
      variables: { GREETING: 'from-e2e' },
    });
    const withDetail = await pollRunToCompletion(page, token, withId);
    expect(withDetail.status).toBe('passed');
    const stdout = await getRunStdout(page, token, withId);
    expect(stdout).toContain('Variable Test');
  });

  test('a directory target executes all tests underneath it', async ({ page }) => {
    test.setTimeout(300_000);

    const runId = await startRun(page, token, {
      repository_id: repoId,
      target_path: 'tests/tagged',
    });
    const detail = await pollRunToCompletion(page, token, runId);
    expect(detail.status).toBe('passed');

    const stdout = await getRunStdout(page, token, runId);
    expect(stdout).toContain('Tagged Test');
    expect(stdout).toContain('Untagged Test');
  });

  test('repo tag discovery feeds the run dialog suggestions', async ({ page }) => {
    const res = await page.request.get(`${API}/explorer/${repoId}/tags`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
    const tags = await res.json();
    expect(tags).toContain('smoke');
  });
});
