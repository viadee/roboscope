/**
 * RoboScope Demo Video Recording — Fresh Instance
 *
 * Records a complete feature tour starting from a CLEAN, EMPTY RoboScope.
 * Supports English and German via DEMO_LANG env var.
 *
 * Prerequisites:
 *   - Backend running on http://localhost:8000 with EMPTY database
 *   - Frontend running on http://localhost:5173
 *
 * Run:
 *   cd e2e && npx playwright test tests/take-demo-video.spec.ts --grep "Full"
 *   cd e2e && DEMO_LANG=de npx playwright test tests/take-demo-video.spec.ts --grep "Full"
 *
 * Output:
 *   e2e/demo-video/
 */
import { test } from '@playwright/test';
import path from 'path';

const VIDEO_DIR = path.join(__dirname, '..', 'demo-video');
const BASE = 'http://localhost:5173';
const API = 'http://localhost:8000/api/v1';
const LANG = process.env.DEMO_LANG === 'de' ? 'de' : 'en';

// ---------------------------------------------------------------------------
// i18n: Overlay texts + button labels per language
// ---------------------------------------------------------------------------
const i18n = {
  en: {
    // Overlays
    subtitle: 'Test Management for Robot Framework',
    openSource: 'Open Source  /  Self-Hosted  /  Offline',
    dashboard: 'Dashboard — Everything at a Glance',
    kpiCards: 'KPI Cards: Tests, Success Rate, Trends',
    roles: '4 Roles: Viewer < Runner < Editor < Admin',
    gitIntegration: 'Git Integration — Projects from Repositories',
    examplesNote: 'Examples project — auto-seeded on first start',
    addFromGit: 'Add from Git URL or local folder',
    branchSwitch: 'Branch switching & Environment assignment',
    threeEditors: '3 Editors — Code, Visual, Flow',
    fileTree: 'File tree with test count per folder',
    codeEditor: 'Code Editor with syntax highlighting',
    visualEditor: 'Visual Editor: Structured editing',
    flowEditor: 'Flow Editor: Visual test graph',
    envTitle: 'Package Manager — Environments under Control',
    envFields: 'Name, Python version, optional Docker image',
    packages: 'Packages — install & manage dependencies',
    variables: 'Variables — environment-specific configuration',
    libraryCheck: 'Library Check: Detect missing packages',
    executionTitle: 'Live Execution with WebSocket Streaming',
    run1: 'Run 1: Calculator tests — should pass',
    run2: 'Run 2: Erroneous test — should fail',
    statusBadges: 'Status: pending → running → passed / failed',
    dockerLocal: 'Docker + Local execution supported',
    passedFailed: 'Passed and Failed — clearly visible',
    runDetail: 'Run Detail — Output & Report',
    reportDetail: 'Report Detail — Results & HTML Report',
    reportResults: 'Test results, duration, errors at a glance',
    reportHtml: 'Original HTML report embedded',
    statsTitle: 'Statistics & Deep Analysis',
    statsCallout: 'Success rate, trends, flaky tests',
    kpis15: '15 KPIs in 5 categories',
    kpiCategories: 'Keyword Analytics / Test Quality / Maintenance',
    aiTitle: 'AI-Powered Failure Analysis',
    aiProviders: '4 Providers: OpenAI, Anthropic, Ollama, OpenRouter',
    aiGenerate: '.roboscope YAML → .robot Generation',
    enterprise: 'Enterprise-Ready',
    apiTokens: 'API Tokens for CI/CD Integration',
    webhooks: 'Webhooks + Git Push triggers',
    auditLog: 'Full Audit Log + Retention policies',
    outroLine1: 'Open Source — Self-Hosted — Offline',
    outroLine2: 'github.com/viadee/roboscope',
    outroLine3: 'Try it out!',
    // Button labels (English UI)
    btnAddProject: /add project/i,
    btnCancel: /cancel/i,
    btnVisualEditor: 'Visual Editor',
    btnFlow: 'Flow',
    btnNewEnv: '+ New Environment',
    btnCreate: 'Create',
    btnNewRun: '+ New Run',
    btnStart: 'Start',
    btnDeepAnalysis: 'Deep Analysis',
    btnAI: 'AI & Generation',
    btnTokens: 'API Tokens',
    btnWebhooks: 'Webhooks',
    btnAudit: 'Audit Log',
  },
  de: {
    subtitle: 'Test Management für Robot Framework',
    openSource: 'Open Source  /  Self-Hosted  /  Offline',
    dashboard: 'Dashboard — Alles auf einen Blick',
    kpiCards: 'KPI-Karten: Tests, Erfolgsquote, Trends',
    roles: '4 Rollen: Viewer < Runner < Editor < Admin',
    gitIntegration: 'Git-Integration — Projekte aus Repositories',
    examplesNote: 'Beispiel-Projekt — beim Start automatisch erstellt',
    addFromGit: 'Hinzufügen via Git-URL oder lokalem Ordner',
    branchSwitch: 'Branch-Wechsel & Umgebungszuordnung',
    threeEditors: '3 Editoren — Code, Visual, Flow',
    fileTree: 'Dateibaum mit Testanzahl pro Ordner',
    codeEditor: 'Code-Editor mit Syntax-Highlighting',
    visualEditor: 'Visual Editor: Strukturierte Bearbeitung',
    flowEditor: 'Flow-Editor: Visueller Testablauf',
    envTitle: 'Package Manager — Umgebungen im Griff',
    envFields: 'Name, Python-Version, optionales Docker-Image',
    packages: 'Pakete — installieren & verwalten',
    variables: 'Variablen — umgebungsspezifische Konfiguration',
    libraryCheck: 'Library-Check: Fehlende Pakete erkennen',
    executionTitle: 'Live-Ausführung mit WebSocket-Streaming',
    run1: 'Run 1: Mathe-Tests — sollte bestehen',
    run2: 'Run 2: Fehlerhafter Test — sollte scheitern',
    statusBadges: 'Status: pending → running → passed / failed',
    dockerLocal: 'Docker + lokale Ausführung',
    passedFailed: 'Bestanden und Fehlgeschlagen — klar sichtbar',
    runDetail: 'Run-Detail — Output & Report',
    reportDetail: 'Report-Detail — Ergebnisse & HTML-Report',
    reportResults: 'Testergebnisse, Dauer, Fehler auf einen Blick',
    reportHtml: 'Originaler HTML-Report eingebettet',
    statsTitle: 'Statistiken & Tiefenanalyse',
    statsCallout: 'Erfolgsquote, Trends, Flaky Tests',
    kpis15: '15 KPIs in 5 Kategorien',
    kpiCategories: 'Keyword Analytics / Test Quality / Maintenance',
    aiTitle: 'KI-gestützte Fehleranalyse',
    aiProviders: '4 Anbieter: OpenAI, Anthropic, Ollama, OpenRouter',
    aiGenerate: '.roboscope YAML → .robot Generierung',
    enterprise: 'Enterprise-Ready',
    apiTokens: 'API-Tokens für CI/CD-Integration',
    webhooks: 'Webhooks + Git-Push-Trigger',
    auditLog: 'Vollständiges Audit-Log + Aufbewahrung',
    outroLine1: 'Open Source — Self-Hosted — Offline',
    outroLine2: 'github.com/viadee/roboscope',
    outroLine3: 'Probiert es aus!',
    // Button labels (German UI)
    btnAddProject: /projekt hinzuf/i,
    btnCancel: /abbrechen/i,
    btnVisualEditor: 'Visual Editor',
    btnFlow: 'Flow',
    btnNewEnv: '+ Neue Umgebung',
    btnCreate: 'Erstellen',
    btnNewRun: '+ Neuer Run',
    btnStart: 'Starten',
    btnDeepAnalysis: 'Tiefenanalyse',
    btnAI: 'KI & Generierung',
    btnTokens: 'API-Tokens',
    btnWebhooks: 'Webhooks',
    btnAudit: 'Audit-Log',
  },
} as const;

const t = i18n[LANG];

// ---------------------------------------------------------------------------
// Overlay helpers (same as before)
// ---------------------------------------------------------------------------

async function injectOverlayStyles(page: import('@playwright/test').Page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-overlay-styles')) return;
    const style = document.createElement('style');
    style.id = 'demo-overlay-styles';
    style.textContent = `
      .demo-overlay{position:fixed;z-index:99999;pointer-events:none;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;opacity:0;transition:opacity .5s ease,transform .4s ease}
      .demo-overlay.visible{opacity:1}
      .demo-overlay.scene-title{top:80px;left:50%;transform:translateX(-50%) translateY(-10px);background:rgba(26,45,80,.92);color:#fff;font-size:28px;font-weight:700;padding:16px 36px;border-radius:12px;text-align:center;white-space:nowrap;box-shadow:0 8px 32px rgba(0,0,0,.3)}
      .demo-overlay.scene-title.visible{transform:translateX(-50%) translateY(0)}
      .demo-overlay.feature-tag{bottom:40px;left:40px;background:#3B7DD8;color:#fff;font-size:18px;font-weight:600;padding:10px 24px;border-radius:8px;transform:translateX(-30px);box-shadow:0 4px 16px rgba(59,125,216,.4)}
      .demo-overlay.feature-tag.visible{transform:translateX(0)}
      .demo-overlay.feature-tag-center{bottom:120px;left:50%;background:#3B7DD8;color:#fff;font-size:22px;font-weight:600;padding:14px 32px;border-radius:10px;transform:translateX(-50%) scale(.9);box-shadow:0 4px 16px rgba(59,125,216,.4);text-align:center}
      .demo-overlay.feature-tag-center.visible{transform:translateX(-50%) scale(1)}
      .demo-overlay.big-title{top:50%;left:50%;transform:translate(-50%,-50%) scale(.8);background:rgba(26,45,80,.95);color:#fff;font-size:42px;font-weight:800;padding:24px 56px;border-radius:16px;text-align:center;white-space:nowrap;box-shadow:0 12px 48px rgba(0,0,0,.4);letter-spacing:1px}
      .demo-overlay.big-title.visible{transform:translate(-50%,-50%) scale(1)}
      .demo-overlay.callout{background:#fff;color:#1A1D2E;font-size:16px;font-weight:500;padding:12px 20px;border-radius:8px;border:2px solid #D4883E;box-shadow:0 4px 16px rgba(0,0,0,.15);max-width:300px;transform:scale(.85)}
      .demo-overlay.callout.visible{transform:scale(1)}
    `;
    document.head.appendChild(style);
  });
}

async function showOverlay(page: import('@playwright/test').Page, type: string, text: string, ms: number, pos?: Record<string, string>) {
  const id = `ov-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  await page.evaluate(({ id, type, text, pos }) => {
    const el = document.createElement('div'); el.id = id; el.className = `demo-overlay ${type}`; el.textContent = text;
    if (pos) Object.entries(pos).forEach(([k, v]) => { (el.style as any)[k] = v; });
    document.body.appendChild(el); void el.offsetHeight; el.classList.add('visible');
  }, { id, type, text, pos });
  await page.waitForTimeout(ms);
  await page.evaluate((id) => { const el = document.getElementById(id); if (el) { el.classList.remove('visible'); setTimeout(() => el.remove(), 600); } }, id).catch(() => {});
  await page.waitForTimeout(300);
}

function bg(page: import('@playwright/test').Page, type: string, text: string, ms: number, pos?: Record<string, string>) {
  showOverlay(page, type, text, ms, pos).catch(() => {});
}

async function wait(page: import('@playwright/test').Page, ms: number) { await page.waitForTimeout(ms); }

async function login(page: import('@playwright/test').Page) {
  const res = await page.request.post(`${API}/auth/login`, { data: { email: 'admin@roboscope.local', password: 'admin123' } });
  const body = await res.json();
  // CRITICAL: the router guard (router/index.ts) redirects EVERY route to
  // /welcome while `user.first_login_complete === false`. On a fresh demo DB
  // the seeded admin has it false, so without this the whole tour renders the
  // onboarding screen instead of the real feature pages. Mark it complete
  // (server-side, persistent) before the SPA ever loads the user.
  await page.request.patch(`${API}/auth/me/first-login-complete`, {
    headers: { Authorization: `Bearer ${body.access_token}` },
    data: { value: true },
  }).catch(() => {});
  await page.evaluate(({ tokens, lang }) => {
    localStorage.setItem('access_token', tokens.access_token);
    localStorage.setItem('refresh_token', tokens.refresh_token);
    localStorage.setItem('roboscope_tour_completed', 'true');
    localStorage.setItem('lang', lang);
  }, { tokens: body, lang: LANG });
}

async function nav(page: import('@playwright/test').Page, p: string) {
  await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle' }); await injectOverlayStyles(page); await wait(page, 800);
}

// ---------------------------------------------------------------------------
// MAIN DEMO VIDEO
// ---------------------------------------------------------------------------

test.describe('Demo Video Recording', () => {
  test.setTimeout(2_400_000);

  test(`Full Feature Tour [${LANG.toUpperCase()}]`, async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      recordVideo: { dir: VIDEO_DIR, size: { width: 1920, height: 1080 } },
    });
    const page = await context.newPage();

    // === SCENE 1 — INTRO ===
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await login(page);
    await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' });
    await injectOverlayStyles(page);

    await showOverlay(page, 'big-title', 'RoboScope', 3500);
    await showOverlay(page, 'feature-tag-center', t.subtitle, 3000);
    await showOverlay(page, 'feature-tag-center', t.openSource, 3000);
    await wait(page, 500);

    // === SCENE 2 — DASHBOARD ===
    bg(page, 'scene-title', t.dashboard, 5000);
    await wait(page, 2000);
    bg(page, 'callout', t.kpiCards, 4000, { top: '200px', right: '60px', left: 'auto' });
    await wait(page, 3000);
    bg(page, 'feature-tag', t.roles, 3500);
    await wait(page, 4000);

    // === SCENE 3 — PROJECTS & GIT ===
    await nav(page, '/repos');
    bg(page, 'scene-title', t.gitIntegration, 5000);
    await wait(page, 2000);

    const examplesCard = page.locator('.card').filter({ hasText: /examples/i }).first();
    if (await examplesCard.isVisible({ timeout: 3000 }).catch(() => false)) {
      bg(page, 'callout', t.examplesNote, 3500, { top: '250px', left: '350px' });
      await wait(page, 4000);
    }

    const addBtn = page.getByRole('button', { name: t.btnAddProject });
    if (await addBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await addBtn.click(); await wait(page, 1000);
      bg(page, 'feature-tag', t.addFromGit, 3000);
      await wait(page, 3000);
      const cancelBtn = page.getByRole('button', { name: t.btnCancel });
      if (await cancelBtn.isVisible({ timeout: 2000 }).catch(() => false)) await cancelBtn.click();
      else await page.keyboard.press('Escape');
      await wait(page, 500);
    }

    bg(page, 'feature-tag', t.branchSwitch, 3500);
    await wait(page, 4000);

    const exploreLink = page.locator('a[href*="/explorer"]').first();
    if (await exploreLink.isVisible({ timeout: 2000 }).catch(() => false)) {
      await exploreLink.click(); await page.waitForLoadState('networkidle');
    } else { await nav(page, '/explorer'); }

    // === SCENE 4 — EXPLORER & EDITORS ===
    await injectOverlayStyles(page); await wait(page, 1500);
    bg(page, 'scene-title', t.threeEditors, 5000);
    await wait(page, 2000);

    const calcFolder = page.locator('text=calculator').first();
    if (await calcFolder.isVisible({ timeout: 3000 }).catch(() => false)) { await calcFolder.click(); await wait(page, 1500); }
    bg(page, 'callout', t.fileTree, 3500, { top: '350px', left: '20px' });

    const robotFile = page.locator('text=basic_math.robot').first();
    if (await robotFile.isVisible({ timeout: 3000 }).catch(() => false)) { await robotFile.click(); await wait(page, 2500); }
    await wait(page, 2000);

    bg(page, 'feature-tag', t.codeEditor, 3000); await wait(page, 3000);

    const visualTab = page.getByRole('button', { name: t.btnVisualEditor });
    if (await visualTab.isVisible({ timeout: 2000 }).catch(() => false)) {
      await visualTab.click(); await wait(page, 1500);
      bg(page, 'feature-tag', t.visualEditor, 3500); await wait(page, 3500);
    }

    const flowTab = page.getByRole('button', { name: t.btnFlow });
    if (await flowTab.isVisible({ timeout: 2000 }).catch(() => false)) {
      await flowTab.click(); await wait(page, 2000);
      bg(page, 'feature-tag', t.flowEditor, 4000); await wait(page, 4000);
    }

    // === SCENE 5 — ENVIRONMENT ===
    await nav(page, '/environments');
    bg(page, 'scene-title', t.envTitle, 5000); await wait(page, 2000);

    // Step 1: Create environment
    const newEnvBtn = page.getByRole('button', { name: t.btnNewEnv });
    if (await newEnvBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await newEnvBtn.click(); await wait(page, 1000);
      const nameInput = page.locator('input[placeholder="production"]');
      if (await nameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await nameInput.clear(); await nameInput.fill('demo-environment'); await wait(page, 500);
      }
      bg(page, 'feature-tag', t.envFields, 3000); await wait(page, 2000);
      const createBtn = page.getByRole('button', { name: t.btnCreate });
      if (await createBtn.isVisible({ timeout: 2000 }).catch(() => false)) { await createBtn.click(); await wait(page, 6000); }
    }

    // Reload to see the created environment
    await nav(page, '/environments');

    // Step 2: Expand, open Install dialog, and install robotframework
    const envName = page.locator('text=demo-environment').first();
    if (await envName.isVisible({ timeout: 5000 }).catch(() => false)) {
      await envName.click(); await wait(page, 1500);

      // Open Install Package dialog
      const installPkgBtn = page.getByRole('button', { name: /install|paket/i });
      if (await installPkgBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await installPkgBtn.click();
        await wait(page, 1500);

        bg(page, 'callout', t.libraryCheck, 4000, { top: '180px', right: '60px', left: 'auto' });
        await wait(page, 2000);

        // Click the first "Installieren"/"Install" button (robotframework is typically first)
        const installBtns = page.locator('.modal button').filter({ hasText: /^install|^Installieren$/i });
        const firstInstall = installBtns.first();
        if (await firstInstall.isVisible({ timeout: 2000 }).catch(() => false)) {
          await firstInstall.click();
          bg(page, 'feature-tag', t.packages, 3000);
          // Wait for installation to complete (~10-15s)
          await wait(page, 15000);
        }

        // Close dialog
        await page.keyboard.press('Escape');
        await wait(page, 500);
      }
    }

    // Step 3: Reload and show the fully populated environment card
    await nav(page, '/environments');
    await wait(page, 1000);

    const envName2 = page.locator('text=demo-environment').first();
    if (await envName2.isVisible({ timeout: 5000 }).catch(() => false)) {
      await envName2.click(); await wait(page, 2000);

      // Scroll into view
      await envName2.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      await wait(page, 1000);

      // Show Packages section (now with robotframework installed)
      bg(page, 'callout', t.packages, 4000, { top: '350px', right: '60px', left: 'auto' });
      await wait(page, 4000);

      // Scroll down to see Docker section + Variables + Clone/Delete
      await page.evaluate(() => window.scrollBy(0, 400));
      await wait(page, 1000);

      bg(page, 'callout', t.variables, 4000, { top: '400px', right: '60px', left: 'auto' });
      await wait(page, 4000);

      // Scroll back to top
      await page.evaluate(() => window.scrollTo(0, 0));
      await wait(page, 500);
    }

    // === SCENE 6 — TEST EXECUTION ===
    await nav(page, '/runs');
    bg(page, 'scene-title', t.executionTitle, 5000); await wait(page, 2000);

    async function startRun(target: string) {
      // Best-effort for the capture tour: the run-creation modal UI may have
      // drifted from this script, but the tour must never abort mid-recording
      // over one click (the run-start flow itself is covered by the real e2e
      // suite). Every interaction is guarded + swallows so the video completes.
      try {
        const runBtn = page.getByRole('button', { name: t.btnNewRun });
        if (!(await runBtn.isVisible({ timeout: 3000 }).catch(() => false))) return;
        await runBtn.click({ timeout: 5000 }).catch(() => {}); await wait(page, 1000);
        const sel = page.locator('.modal select, select').first();
        if (await sel.isVisible({ timeout: 2000 }).catch(() => false)) {
          await sel.selectOption({ index: 1 }).catch(() => {}); await wait(page, 500);
        }
        const inp = page.locator('.modal input[placeholder*="tests"], input[placeholder*="tests"]').first();
        if (await inp.isVisible({ timeout: 2000 }).catch(() => false)) {
          await inp.clear().catch(() => {}); await inp.fill(target).catch(() => {}); await wait(page, 500);
        }
        const btn = page.getByRole('button', { name: t.btnStart });
        if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await btn.click({ timeout: 5000 }).catch(() => {}); await wait(page, 1500);
        }
        // Close any leftover modal so the tour continues cleanly.
        await page.keyboard.press('Escape').catch(() => {});
      } catch {
        // never abort the recording over a run-start hiccup
      }
    }

    bg(page, 'callout', t.run1, 4000, { top: '200px', right: '60px', left: 'auto' });
    await startRun('calculator/basic_math.robot'); await wait(page, 2000);

    bg(page, 'callout', t.run2, 4000, { top: '200px', right: '60px', left: 'auto' });
    await startRun('api_testing/errorneus.robot'); await wait(page, 2000);

    bg(page, 'feature-tag', t.statusBadges, 4000); await wait(page, 3000);
    bg(page, 'feature-tag', t.dockerLocal, 3000); await wait(page, 3000);

    // Wait for runs to complete — poll until we see passed/failed badges
    for (let i = 0; i < 6; i++) {
      await wait(page, 3000);
      await page.reload({ waitUntil: 'networkidle' });
      await injectOverlayStyles(page);
      const passedBadge = page.locator('text=passed').first();
      if (await passedBadge.isVisible({ timeout: 1000 }).catch(() => false)) break;
    }
    await wait(page, 2000);

    bg(page, 'callout', t.passedFailed, 3500, { top: '250px', right: '60px', left: 'auto' }); await wait(page, 4000);

    // === SCENE 6b — REPORT DETAIL ===
    // Click the PASSED run row (look for "passed" text in table)
    const passedRow = page.locator('table tbody tr').filter({ hasText: /passed/i }).first();
    const firstRow = page.locator('table tbody tr').first();
    const targetRow = await passedRow.isVisible({ timeout: 2000 }).catch(() => false) ? passedRow : firstRow;

    if (await targetRow.isVisible({ timeout: 3000 }).catch(() => false)) {
      await targetRow.click(); await wait(page, 2000);
      bg(page, 'scene-title', t.runDetail, 5000); await wait(page, 2000);
      const outputBtn = page.getByRole('button', { name: /output/i });
      if (await outputBtn.isVisible({ timeout: 2000 }).catch(() => false)) { await outputBtn.click(); await wait(page, 3000); }
    }

    // Navigate to report — look for report link in detail panel or via direct URL
    const reportLink = page.locator('a[href*="/reports/"]').first();
    if (await reportLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await reportLink.click(); await page.waitForLoadState('networkidle');
      await injectOverlayStyles(page); await wait(page, 2000);
      bg(page, 'scene-title', t.reportDetail, 5000); await wait(page, 2000);
      bg(page, 'callout', t.reportResults, 3500, { top: '200px', right: '60px', left: 'auto' }); await wait(page, 4000);
      bg(page, 'feature-tag', t.reportHtml, 3000); await wait(page, 4000);
    }

    // === SCENE 7 — STATISTICS ===
    await nav(page, '/stats');
    bg(page, 'scene-title', t.statsTitle, 5000); await wait(page, 2000);
    bg(page, 'callout', t.statsCallout, 3500, { top: '200px', left: '350px' }); await wait(page, 3000);

    const deepTab = page.getByRole('button', { name: t.btnDeepAnalysis });
    if (await deepTab.isVisible({ timeout: 2000 }).catch(() => false)) { await deepTab.click(); await wait(page, 1500); }
    bg(page, 'feature-tag', t.kpis15, 3500); await wait(page, 2000);
    bg(page, 'feature-tag', t.kpiCategories, 3500); await wait(page, 4000);

    // === SCENE 8 — AI ===
    await nav(page, '/settings');
    const aiTab = page.getByRole('button', { name: t.btnAI });
    if (await aiTab.isVisible({ timeout: 3000 }).catch(() => false)) { await aiTab.click(); await wait(page, 1000); }
    bg(page, 'scene-title', t.aiTitle, 5000); await wait(page, 2000);
    bg(page, 'feature-tag', t.aiProviders, 3500); await wait(page, 4000);
    bg(page, 'feature-tag', t.aiGenerate, 3500); await wait(page, 4000);

    // === SCENE 9 — ENTERPRISE ===
    const tokensTab = page.getByRole('button', { name: t.btnTokens });
    if (await tokensTab.isVisible({ timeout: 2000 }).catch(() => false)) { await tokensTab.click(); await wait(page, 800); }
    bg(page, 'scene-title', t.enterprise, 5000); await wait(page, 1000);
    bg(page, 'feature-tag', t.apiTokens, 3000); await wait(page, 3500);

    const webhooksTab = page.getByRole('button', { name: t.btnWebhooks });
    if (await webhooksTab.isVisible({ timeout: 2000 }).catch(() => false)) { await webhooksTab.click(); await wait(page, 800); }
    bg(page, 'feature-tag', t.webhooks, 3000); await wait(page, 3500);

    const auditTab = page.getByRole('button', { name: t.btnAudit });
    if (await auditTab.isVisible({ timeout: 2000 }).catch(() => false)) { await auditTab.click(); await wait(page, 800); }
    bg(page, 'feature-tag', t.auditLog, 3000); await wait(page, 4000);

    // =====================================================================
    // DEEP DIVE — FULL-FLEDGED EXECUTION OF EVERY FEATURE + EDGE CASES
    // (real interactions, German UI; selectors harvested from the green e2e specs)
    // =====================================================================
    const cap = (o: { en: string; de: string }) => (LANG === 'de' ? o.de : o.en);
    const clickIf = async (loc: import('@playwright/test').Locator, ms = 1200) => {
      if (await loc.isVisible({ timeout: 2500 }).catch(() => false)) {
        await loc.click({ timeout: 6000 }).catch(() => {}); await wait(page, ms); return true;
      }
      return false;
    };
    const sceneCap = async (o: { en: string; de: string }, ms = 4200) => {
      await showOverlay(page, 'scene-title', cap(o), ms);
    };
    const tag = async (o: { en: string; de: string }, ms = 3800) => {
      await showOverlay(page, 'feature-tag', cap(o), ms);
    };
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    const authH = { Authorization: `Bearer ${token}` };
    // Resolve the seeded "Examples" repo id for explorer/run flows.
    let repoId = 1;
    try {
      const rr = await page.request.get(`${API}/repos`, { headers: authH });
      const repos = await rr.json();
      const list = Array.isArray(repos) ? repos : (repos.items || repos.repositories || []);
      // Prefer the LOCAL "Examples" repo (has calculator/basic_math.robot on
      // disk). The git-clone "Robot Framework Examples" may be empty offline.
      const ex = list.find((r: any) => r.name === 'Examples')
        || list.find((r: any) => r.repo_type === 'local')
        || list.find((r: any) => /example/i.test(r.name)) || list[0];
      if (ex) repoId = ex.id;
    } catch { /* fall back to 1 */ }

    await showOverlay(page, 'big-title',
      cap({ en: 'Deep Dive — Every Feature, Live', de: 'Deep Dive — Jedes Feature, live' }), 3800);

    // ---- A · AUTH / RBAC (real wrong-login + viewer read-only) ----------
    await sceneCap({ en: 'A · Auth & Roles', de: 'A · Auth & Rollen' });
    await page.evaluate(() => localStorage.removeItem('access_token'));
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' }); await injectOverlayStyles(page);
    const eIn = page.locator('input[type="email"], input[type="text"]').first();
    const pIn = page.locator('input[type="password"]').first();
    if (await eIn.isVisible({ timeout: 4000 }).catch(() => false)) {
      await eIn.fill('admin@roboscope.local').catch(() => {});
      await pIn.fill('falsch-falsch').catch(() => {});
      await tag({ en: 'Edge: wrong password → inline error', de: 'Edge: falsches Passwort → Inline-Fehler' }, 1200);
      await clickIf(page.getByRole('button', { name: /anmelden|login|sign in/i }), 2500);
      await tag({ en: 'Login is rejected — try again', de: 'Login wird abgewiesen — erneut versuchen' }, 3500);
    }
    await login(page);
    // Create + log in as a VIEWER → real read-only dashboard.
    await page.request.post(`${API}/auth/users`, { headers: authH,
      data: { email: 'viewer@demo.local', username: 'viewer', password: 'viewer123', role: 'viewer' } }).catch(() => {});
    const vr = await page.request.post(`${API}/auth/login`, { data: { email: 'viewer@demo.local', password: 'viewer123' } }).catch(() => null);
    if (vr && vr.ok()) {
      const vb = await vr.json();
      await page.request.patch(`${API}/auth/me/first-login-complete`, { headers: { Authorization: `Bearer ${vb.access_token}` }, data: { value: true } }).catch(() => {});
      await page.evaluate((tok) => { localStorage.setItem('access_token', tok.access_token); localStorage.setItem('refresh_token', tok.refresh_token); localStorage.setItem('roboscope_tour_completed', 'true'); }, vb);
      await nav(page, '/dashboard');
      await tag({ en: 'VIEWER role — read-only (no Recorder/Environments)', de: 'VIEWER-Rolle — nur lesend (kein Recorder/Umgebungen)' }, 4000);
    }
    await login(page);

    // ---- C · EXPLORER & EDITORS (real tree, tabs, create, search) -------
    await sceneCap({ en: 'C · Explorer & Editors', de: 'C · Explorer & Editoren' });
    await nav(page, `/explorer/${repoId}`);
    await page.locator('.tree-content').isVisible({ timeout: 8000 }).catch(() => false);
    await clickIf(page.locator('.tree-node .node-name', { hasText: /^calculator$/ }), 800);
    await clickIf(page.locator('.node-name', { hasText: 'basic_math.robot' }), 1500);
    await tag({ en: 'File tree · test count per folder', de: 'Dateibaum · Testanzahl pro Ordner' }, 3000);
    await clickIf(page.locator('button.tab-btn, .tab-btn', { hasText: 'Code' }).first(), 1200);
    await tag({ en: 'Code editor — syntax highlighting', de: 'Code-Editor — Syntax-Highlighting' }, 3000);
    await clickIf(page.locator('button', { hasText: /^Flow$/ }).first(), 1500);
    await tag({ en: 'Flow editor — visual test graph', de: 'Flow-Editor — visueller Testgraph' }, 3500);
    await clickIf(page.locator('button.tab-btn', { hasText: /(visual|visuel)/i }).first(), 1200);
    await tag({ en: 'Visual editor — structured editing', de: 'Visual-Editor — strukturierte Bearbeitung' }, 3000);
    // Real create-file dialog
    if (await clickIf(page.getByRole('button', { name: '+' }).first(), 800)) {
      const nf = page.locator('input[placeholder*="tests/neue_tests"], input[placeholder*="tests/neue"]').first();
      if (await nf.isVisible({ timeout: 2000 }).catch(() => false)) {
        await nf.fill('tests/demo_created.robot').catch(() => {});
        await tag({ en: 'Create / rename / delete files', de: 'Dateien anlegen / umbenennen / löschen' }, 2500);
        await clickIf(page.getByRole('button', { name: 'Anlegen' }), 1500);
      } else { await page.keyboard.press('Escape').catch(() => {}); }
    }
    // Real search
    const searchInp = page.locator('input[placeholder*="suchen"], input[placeholder*="search"]').first();
    if (await searchInp.isVisible({ timeout: 2000 }).catch(() => false)) {
      await searchInp.fill('Test').catch(() => {});
      await clickIf(page.getByRole('button', { name: /suchen|search/i }), 2000);
      await tag({ en: 'Full-text search across the repo', de: 'Volltextsuche über das Repo' }, 3000);
    }

    // ---- I · SELF-HEALING (real per-step + suite toggle) ----------------
    await sceneCap({ en: 'I · Self-Healing', de: 'I · Self-Healing' });
    const healRobot = [
      '*** Settings ***', 'Library    Browser', '',
      '*** Test Cases ***', 'Heal Demo',
      '    Click    text=Submit', '    Fill Text    id=user    alice', '    Log    done', '',
    ].join('\n');
    await page.request.post(`${API}/explorer/${repoId}/file`, { headers: authH, data: { path: 'tests/heal_demo.robot', content: healRobot } }).catch(() => {});
    await nav(page, `/explorer/${repoId}`);
    await clickIf(page.locator('.tree-node .node-name', { hasText: /^tests$/ }), 600);
    await clickIf(page.locator('.node-name', { hasText: 'heal_demo.robot' }), 1500);
    await clickIf(page.locator('button', { hasText: /^Flow$/ }).first(), 1500);
    const clickNode = page.locator('.vue-flow__node', { has: page.locator('.flow-node-label:text-is("Click")') }).first();
    if (await clickNode.isVisible({ timeout: 4000 }).catch(() => false)) {
      await clickNode.click().catch(() => {}); await wait(page, 800);
      const healToggle = page.getByTestId('flow-step-heal-toggle');
      if (await healToggle.isVisible({ timeout: 2000 }).catch(() => false)) {
        await tag({ en: 'Opt-in per step: enable healing on "Click"', de: 'Opt-in pro Step: Healing für "Click" aktivieren' }, 2000);
        await healToggle.check().catch(() => {}); await wait(page, 1200);
      }
    }
    // Non-healable edge: Log node has no toggle
    const logNode = page.locator('.vue-flow__node', { has: page.locator('.flow-node-label:text-is("Log")') }).first();
    if (await logNode.isVisible({ timeout: 2000 }).catch(() => false)) {
      await logNode.click().catch(() => {}); await wait(page, 800);
      await tag({ en: 'Edge: "Log" is non-healable → no toggle', de: 'Edge: "Log" ist nicht heilbar → kein Toggle' }, 3000);
    }
    await clickIf(page.locator('.tab-btn', { hasText: 'Code' }).first(), 1200);
    await tag({ en: 'Code now shows "Heal Click" — plain Click untouched', de: 'Code zeigt "Heal Click" — Click bleibt unberührt' }, 4000);

    // ---- D · EXECUTION (REAL runs: pass + fail, live status, real output) --
    await sceneCap({ en: 'D · Live Execution', de: 'D · Live-Ausführung' });
    await page.request.post(`${API}/runs/cancel-all`, { headers: authH }).catch(() => {});
    await wait(page, 1500);
    // Show the real run-creation modal once (this is how a user starts a run).
    await nav(page, '/runs');
    await tag({ en: 'Run 1: calculator/basic_math.robot → PASS', de: 'Run 1: calculator/basic_math.robot → BESTEHT' }, 2200);
    if (await clickIf(page.getByRole('button', { name: /Neuer Run|New Run/ }), 1000)) {
      // Pick the local Examples repo by label (falls back to first real option).
      await page.locator('select').first().selectOption({ label: 'Examples' })
        .catch(async () => { await page.locator('select').first().selectOption({ index: 1 }).catch(() => {}); });
      await wait(page, 500);
      const pathInp = page.getByPlaceholder(/tests\/ oder|tests\/login|tests\//).first();
      await pathInp.fill('calculator/basic_math.robot').catch(() => {});
      await wait(page, 1200);
      await clickIf(page.getByRole('button', { name: 'Starten', exact: true }), 1000);
      // Edge: environment-setup dialog — run without provisioning.
      if (await page.getByText(/Umgebung einrichten\?|Set up environment/).isVisible({ timeout: 2500 }).catch(() => false)) {
        await tag({ en: 'Edge: environment setup prompt → run anyway', de: 'Edge: Umgebungs-Setup-Dialog → trotzdem starten' }, 2200);
        await clickIf(page.getByRole('button', { name: /Nein, ohne starten|without/ }), 1000);
      }
      await page.keyboard.press('Escape').catch(() => {});
    }
    // GUARANTEE real execution via the proven API path (the modal above may or
    // may not have dispatched depending on which repo option was picked). These
    // POSTs genuinely run Robot Framework and produce real output + reports.
    const runIds: number[] = [];
    for (const target of ['calculator/basic_math.robot', 'api_testing/errorneus.robot']) {
      const r = await page.request.post(`${API}/runs`, { headers: authH,
        data: { repository_id: repoId, target_path: target } }).catch(() => null);
      if (r && r.ok()) { const j = await r.json(); if (j && j.id) runIds.push(j.id); }
    }
    await tag({ en: 'Run 2: api_testing/errorneus.robot → FAIL', de: 'Run 2: api_testing/errorneus.robot → SCHEITERT' }, 2500);
    // Show the live table updating while the single-worker executor drains the
    // queue (pending → running → passed/failed). Poll real status via the API.
    const TERMINAL = new Set(['passed', 'failed', 'error', 'timeout', 'cancelled']);
    let passedId: number | null = null, failedId: number | null = null;
    await tag({ en: 'Status streams live: pending → running → passed/failed', de: 'Status live: pending → running → passed/failed' }, 3500);
    for (let i = 0; i < 100; i++) {
      await wait(page, 3000);
      await page.reload({ waitUntil: 'networkidle' }).catch(() => {}); await injectOverlayStyles(page);
      let allTerm = runIds.length > 0;
      for (const id of runIds) {
        const d = await page.request.get(`${API}/runs/${id}`, { headers: authH })
          .then((x) => x.json()).catch(() => ({} as any));
        if (!TERMINAL.has(d.status)) allTerm = false;
        if (d.status === 'passed') passedId = id;
        if (['failed', 'error', 'timeout'].includes(d.status)) failedId = id;
      }
      if (allTerm) break;
    }
    // Open the FAILED run's detail panel + real Output modal.
    const targetRunId = failedId ?? passedId ?? runIds[0] ?? null;
    if (targetRunId) {
      await nav(page, `/runs?run=${targetRunId}`);
      const detailRow = page.locator('.data-table tbody tr.clickable-row, .data-table tbody tr').first();
      if (await clickIf(detailRow, 1500)) {
        await tag({ en: 'Run detail — duration, KPIs, AI failure analysis', de: 'Run-Detail — Dauer, KPIs, KI-Fehleranalyse' }, 3500);
      }
      if (await clickIf(page.getByRole('button', { name: 'Output' }).first(), 2000)) {
        await tag({ en: 'Real console output (stdout / stderr)', de: 'Echte Konsolenausgabe (stdout / stderr)' }, 4000);
        await page.keyboard.press('Escape').catch(() => {});
      }
    }

    // ---- J · INTERACTIVE DEBUGGER (real, on a failed run) --------------
    await sceneCap({ en: 'J · Interactive Debugger', de: 'J · Interaktiver Debugger' });
    let failedId: number | null = null;
    try {
      const rr = await page.request.get(`${API}/runs?page=1`, { headers: authH });
      const data = await rr.json();
      const runs = data.items || data.runs || data || [];
      const f = (Array.isArray(runs) ? runs : []).find((r: any) => /fail|error/i.test(r.status));
      if (f) failedId = f.id;
    } catch { /* */ }
    if (failedId) {
      await nav(page, `/runs?run=${failedId}`);
      const dbg = page.getByTestId('debug-btn');
      if (await clickIf(dbg, 2500)) {
        await tag({ en: 'Re-run to the failing keyword · breakpoint set', de: 'Re-run bis zum fehlschlagenden Keyword · Breakpoint' }, 3500);
        if (await page.getByTestId('debug-prereq-dialog').isVisible({ timeout: 2000 }).catch(() => false)) {
          await tag({ en: 'Edge: RobotCode missing → one-click install', de: 'Edge: RobotCode fehlt → Ein-Klick-Installation' }, 3500);
          await clickIf(page.getByTestId('debug-prereq-cancel-btn'), 800);
        }
      }
    }
    await tag({ en: 'Step / continue · scope tree · run-up-to-here', de: 'Step / Continue · Scope-Baum · Bis-hier-ausführen' }, 3500);

    // ---- D2 · SCHEDULES (real cron preset) -----------------------------
    await sceneCap({ en: 'D · Scheduling (cron)', de: 'D · Zeitpläne (Cron)' });
    await nav(page, '/runs');
    await clickIf(page.locator('.tab-btn', { hasText: /Schedules|Zeitpläne/ }), 1200);
    if (await clickIf(page.locator('button', { hasText: /New Schedule|Neuer Zeitplan/ }), 1200)) {
      await clickIf(page.locator('.preset-btn', { hasText: /Hourly|Stündlich/ }), 1500);
      await tag({ en: 'Cron editor: presets → live preview (0 * * * *)', de: 'Cron-Editor: Presets → Live-Vorschau (0 * * * *)' }, 4000);
      await page.keyboard.press('Escape').catch(() => {});
    }

    // ---- E · ENVIRONMENTS & LIBRARY CHECK (real) -----------------------
    await sceneCap({ en: 'E · Environments & Packages', de: 'E · Umgebungen & Pakete' });
    await nav(page, '/environments');
    if (await clickIf(page.getByRole('button', { name: /Neue Umgebung|New Environment/ }), 1000)) {
      await page.getByPlaceholder('production').fill('demo-env').catch(() => {});
      await page.getByPlaceholder('3.12').first().fill('3.12').catch(() => {});
      await tag({ en: 'Create venv (uv): name + Python version', de: 'venv anlegen (uv): Name + Python-Version' }, 3500);
      await clickIf(page.getByRole('button', { name: 'Abbrechen' }), 800);
    }
    await tag({ en: 'Browser + heal auto-provisioned · offline browser-pack', de: 'Browser + Heal auto-provisioniert · Offline-Browser-Pack' }, 3800);

    // ---- F · REPORTS · STATS · HISTORY (real) --------------------------
    await sceneCap({ en: 'F · Reports, Stats & History', de: 'F · Reports, Stats & Historie' });
    await page.goto(`${BASE}/reports/1`, { waitUntil: 'networkidle' }).catch(() => {}); await injectOverlayStyles(page);
    if (await page.locator('.xml-tree, .kpi-card').first().isVisible({ timeout: 4000 }).catch(() => false)) {
      await tag({ en: 'Report detail: KPIs, keyword tree, HTML report', de: 'Report-Detail: KPIs, Keyword-Baum, HTML-Report' }, 3500);
      await clickIf(page.locator('.suite-header').first(), 1500);
      await clickIf(page.locator('.tab-btn').nth(1), 2500);
    }
    await nav(page, '/stats');
    await tag({ en: 'Statistics — KPIs, trends, flakiness', de: 'Statistiken — KPIs, Trends, Flakiness' }, 3000);
    await clickIf(page.getByText(/Tiefenanalyse|Deep Analysis/), 1500);
    if (await clickIf(page.getByRole('button', { name: /Neue Analyse|New Analysis/ }), 1200)) {
      await tag({ en: 'Deep analysis: pick KPIs → generate report', de: 'Tiefenanalyse: KPIs wählen → Report erzeugen' }, 3500);
      await page.keyboard.press('Escape').catch(() => {});
    }
    await nav(page, '/test-history');
    await tag({ en: 'Test history: per-test flakiness & quarantine', de: 'Test-Historie: Flakiness pro Test & Quarantäne' }, 3500);

    // ---- ADMIN · USERS · SSO (real user create + IdP dry-run) ---------
    await sceneCap({ en: 'Enterprise · Users, SSO, Teams', de: 'Enterprise · Benutzer, SSO, Teams' });
    await nav(page, '/settings');
    // Settings has a "Benutzer" sub-tab button (no nav-more-toggle needed).
    await clickIf(page.getByRole('button', { name: /^Benutzer$|^Users$/ }), 1000);
    if (await clickIf(page.getByRole('button', { name: /Benutzer hinzufügen|Add user/ }), 1000)) {
      await page.getByPlaceholder('max.mustermann').fill('demo.user').catch(() => {});
      await page.getByPlaceholder('max@example.com').fill('demo.user@demo.local').catch(() => {});
      await page.getByPlaceholder(/Mindestens 6|At least 6/).fill('demo123456').catch(() => {});
      await tag({ en: 'Create user · assign role (4-tier RBAC)', de: 'Benutzer anlegen · Rolle zuweisen (4-Stufen-RBAC)' }, 3000);
      await clickIf(page.getByRole('button', { name: 'Erstellen', exact: true }), 1500);
    }
    await nav(page, '/admin/identity-providers/new');
    if (await page.locator('#idp-name, [data-testid="run-dry-run-btn"]').first().isVisible({ timeout: 3000 }).catch(() => false)) {
      await page.locator('#idp-name').fill('Demo Azure AD').catch(() => {});
      await page.locator('#idp-issuer-url').fill('https://login.microsoftonline.com/demo/v2.0').catch(() => {});
      await page.locator('#idp-client-id').fill('demo-client-id').catch(() => {});
      await tag({ en: 'SSO: Save gated behind a passing dry-run', de: 'SSO: Speichern erst nach bestandenem Dry-Run' }, 3500);
      await clickIf(page.getByTestId('run-dry-run-btn'), 2500);
    }
    await nav(page, '/admin/emergency-bypass');
    await tag({ en: 'Emergency SSO bypass — time-boxed & audited', de: 'Notfall-SSO-Bypass — zeitlich begrenzt & auditiert' }, 3500);

    // === SCENE 10 — OUTRO ===
    await nav(page, '/dashboard');
    await showOverlay(page, 'big-title', t.outroLine1, 3500);
    await showOverlay(page, 'big-title', t.outroLine2, 3500);
    await showOverlay(page, 'feature-tag-center', t.outroLine3, 3000);
    await wait(page, 2000);

    await context.close();
    console.log(`\n>>> Demo video [${LANG.toUpperCase()}] saved to: ${VIDEO_DIR}/`);
  });

  // =========================================================================
  // TEASER
  // =========================================================================
  test('Teaser — 30s Fast Cuts', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      recordVideo: { dir: VIDEO_DIR, size: { width: 1920, height: 1080 } },
    });
    const page = await context.newPage();
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await login(page);

    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
    await injectOverlayStyles(page);
    await showOverlay(page, 'big-title', 'RoboScope', 2500);

    await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' });
    await injectOverlayStyles(page);

    for (const s of [
      { p: '/dashboard', t: 'DASHBOARD' }, { p: '/repos', t: 'PROJECTS' },
      { p: '/explorer', t: 'EDIT' }, { p: '/runs', t: 'EXECUTE' },
      { p: '/stats', t: 'ANALYZE' }, { p: '/environments', t: 'MANAGE' },
    ]) {
      await page.goto(`${BASE}${s.p}`, { waitUntil: 'networkidle' });
      await injectOverlayStyles(page);
      bg(page, 'big-title', s.t, 1800); await wait(page, 1800);
    }

    await page.goto(`${BASE}/settings`, { waitUntil: 'networkidle' });
    await injectOverlayStyles(page);
    await showOverlay(page, 'big-title', '15 KPIs', 1800);
    await showOverlay(page, 'big-title', 'AI-POWERED', 1800);
    await showOverlay(page, 'big-title', 'ENTERPRISE', 1800);

    await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' });
    await injectOverlayStyles(page);
    await showOverlay(page, 'big-title', 'RoboScope', 2500);
    await showOverlay(page, 'feature-tag-center', 'Open Source / github.com/viadee/roboscope', 3000);
    await wait(page, 500);
    await context.close();
  });
});
