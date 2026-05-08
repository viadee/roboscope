import type { DocsContent } from '../types'

const en: DocsContent = [
  // ─── 1. Getting Started ────────────────────────────────────────────
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: '🚀',
    subsections: [
      {
        id: 'overview',
        title: 'What is RoboScope?',
        content: `
<p>
  <strong>RoboScope</strong> is a web-based test management tool designed specifically for
  <em>Robot Framework</em>. It provides an integrated environment for managing test
  repositories, executing test runs, analyzing reports, and tracking statistics &mdash;
  all from a single, modern web interface.
</p>
<h4>Key Capabilities</h4>
<ul>
  <li><strong>Repository Management</strong> &mdash; Connect Git repositories or local folders to organize your test suites.</li>
  <li><strong>Built-in Explorer</strong> &mdash; Browse, edit, and create <code>.robot</code> files directly in the browser with syntax highlighting.</li>
  <li><strong>Test Execution</strong> &mdash; Launch test runs with configurable timeouts, monitor progress in real time via WebSocket, and review output logs.</li>
  <li><strong>Report Analysis</strong> &mdash; View embedded Robot Framework HTML reports, inspect XML output, and download ZIP archives.</li>
  <li><strong>Statistics &amp; Trends</strong> &mdash; Track success rates, pass/fail trends, and detect flaky tests over configurable time periods.</li>
  <li><strong>Environment Management</strong> &mdash; Create isolated Python virtual environments, install packages, and define environment variables.</li>
  <li><strong>Role-Based Access</strong> &mdash; Four permission levels (Viewer, Runner, Editor, Admin) control who can view, run, edit, or administer.</li>
</ul>`,
        tip: 'RoboScope works best with Chromium-based browsers (Chrome, Edge) or Firefox for the full CodeMirror editing experience.'
      },
      {
        id: 'login',
        title: 'Logging In',
        content: `
<p>
  When you first open RoboScope, you will be presented with the <strong>Login</strong> screen.
  Enter your email address and password to authenticate.
</p>
<h4>Default Administrator Account</h4>
<table>
  <thead>
    <tr><th>Field</th><th>Value</th></tr>
  </thead>
  <tbody>
    <tr><td>Email</td><td><code>admin@roboscope.local</code></td></tr>
    <tr><td>Password</td><td><code>admin123</code></td></tr>
  </tbody>
</table>
<p>
  After logging in with the default account, it is <strong>strongly recommended</strong>
  to change the password immediately or create a dedicated admin user and deactivate
  the default one.
</p>
<h4>Session Handling</h4>
<p>
  RoboScope uses JWT-based authentication. Your session token is automatically refreshed
  as long as the application is open. If the token expires (e.g., after a long
  inactivity period), you will be redirected to the login page.
</p>`,
        tip: 'If you forget your password, an admin user can reset it from the Settings page.'
      },
      {
        id: 'ui-layout',
        title: 'UI Layout',
        content: `
<p>The RoboScope interface consists of three main areas:</p>
<ol>
  <li>
    <strong>Sidebar</strong> (left) &mdash; The primary navigation panel. It contains links to
    all major sections: Dashboard, Repositories, Explorer, Execution, Reports,
    Statistics, Environments, and Settings. The sidebar can be collapsed to a slim
    icon-only view (60 px) to maximize content space.
  </li>
  <li>
    <strong>Header</strong> (top) &mdash; Displays the current page title, the logged-in
    user&rsquo;s name and role, a language switcher (DE/EN/FR/ES), and the logout button.
  </li>
  <li>
    <strong>Content Area</strong> (center) &mdash; The main workspace where the selected
    view is rendered. Each view uses cards, tables, and action buttons following the
    RoboScope design system.
  </li>
</ol>
<p>
  The sidebar width is <code>250px</code> when expanded and <code>60px</code> when collapsed.
  The header has a fixed height of <code>56px</code>.
</p>`,
        tip: 'Click the hamburger icon at the top of the sidebar to toggle between expanded and collapsed modes.'
      },
      {
        id: 'roles-permissions',
        title: 'Roles & Permissions',
        content: `
<p>
  RoboScope implements a hierarchical role-based access control (RBAC) system.
  Each higher role inherits all permissions from the roles below it.
</p>
<table>
  <thead>
    <tr>
      <th>Role</th>
      <th>Level</th>
      <th>Permissions</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Viewer</strong></td>
      <td>0</td>
      <td>View dashboards, repositories, reports, statistics. Read-only access.</td>
    </tr>
    <tr>
      <td><strong>Runner</strong></td>
      <td>1</td>
      <td>All Viewer permissions <strong>+</strong> start test runs, cancel runs, cancel all runs.</td>
    </tr>
    <tr>
      <td><strong>Editor</strong></td>
      <td>2</td>
      <td>All Runner permissions <strong>+</strong> add/edit/delete repositories, edit files in Explorer, manage environments.</td>
    </tr>
    <tr>
      <td><strong>Admin</strong></td>
      <td>3</td>
      <td>All Editor permissions <strong>+</strong> manage users, change roles, modify settings, delete all reports.</td>
    </tr>
  </tbody>
</table>
<p>
  The role hierarchy is strictly ordered:
  <code>Viewer &lt; Runner &lt; Editor &lt; Admin</code>. Endpoint guards ensure that
  users cannot perform actions above their assigned level.
</p>`,
        tip: 'When in doubt about what you can do, check your role badge in the header. If a button is missing, you may need a higher role.'
      }
    ]
  },

  // ─── 2. Dashboard ──────────────────────────────────────────────────
  {
    id: 'dashboard',
    title: 'Dashboard',
    icon: '📊',
    subsections: [
      {
        id: 'dashboard-overview',
        title: 'Dashboard Overview',
        content: `
<p>
  The <strong>Dashboard</strong> is the default landing page after login. It is a
  card grid pointing into every navigable section of RoboScope so a fresh user can
  reach Repositories, Explorer, Runs, Statistics, Recorder, Environments, Docs and
  Settings without scanning the sidebar.
</p>
<p>
  Alongside the navigation cards a static <strong>Tip of the day</strong> card
  rotates through 30 RoboScope-specific tips daily. The deeper KPI metrics
  (run counts, success rate, duration trends) live on the <strong>Statistics</strong>
  page; recent runs and run history live on the <strong>Runs</strong> page.
</p>`
      },
      {
        id: 'navigation-cards',
        title: 'Navigation Cards',
        content: `
<p>
  Each card is a clickable shortcut. Hovering reveals an animated chevron and the
  card lifts slightly to confirm the affordance.
</p>
<table>
  <thead><tr><th>Card</th><th>What it points to</th></tr></thead>
  <tbody>
    <tr><td><strong>Projects</strong></td><td>Configure Git or local projects, set sync schedules, manage permissions.</td></tr>
    <tr><td><strong>Explorer</strong></td><td>Browse the file tree, edit Robot tests visually or in code.</td></tr>
    <tr><td><strong>Execution</strong></td><td>Trigger executions, watch live progress, schedule recurring runs.</td></tr>
    <tr><td><strong>Statistics</strong></td><td>Pass/fail trends, flaky tests, self-healing rate.</td></tr>
    <tr><td><strong>Recorder</strong></td><td>Record interactions in a browser, generate Robot tests automatically. (Editor role and above.)</td></tr>
    <tr><td><strong>Environments</strong></td><td>Manage Python virtual envs, install pip packages, build Docker images. (Editor role and above.)</td></tr>
    <tr><td><strong>Docs</strong></td><td>This documentation, fully searchable in four languages.</td></tr>
    <tr><td><strong>Settings</strong></td><td>AI providers, retention, secrets, audit log, compliance settings. (Admin role.)</td></tr>
  </tbody>
</table>
<p>
  Cards visible to a given user respect their role: Recorder + Environments need
  Editor or above; Settings needs Admin.
</p>`,
        tip: 'New to RoboScope? Start with the Projects card — a default "Robot Framework Examples" git project is seeded on first start so you have something to play with right away.'
      },
      {
        id: 'tip-of-the-day',
        title: 'Tip of the Day',
        content: `
<p>
  A small <strong>💡 Tip of the day</strong> card sits inside the grid, surfacing
  one of 30 short RoboScope-specific tips. Tips rotate over a 30-day cycle —
  every calendar day picks a new one — so frequent users learn a new feature
  every time they open the dashboard.
</p>
<p>
  Tips focus on RoboScope features specifically (Flow Editor palette, Recorder
  selector picker, Self-Healing keywords, Stats heal-rate, Repos auto-sync,
  Run-Detail panel, …) — not generic Robot Framework tips. The tip text is
  available in all four locales (EN/DE/FR/ES).
</p>`
      }
    ]
  },

  // ─── 3. Repositories ──────────────────────────────────────────────
  {
    id: 'repositories',
    title: 'Repositories',
    icon: '📁',
    subsections: [
      {
        id: 'repos-overview',
        title: 'Repository Management',
        content: `
<p>
  The <strong>Repositories</strong> page is where you register and manage your Robot Framework
  test repositories. RoboScope supports two types of repositories:
</p>
<ul>
  <li><strong>Git Repositories</strong> &mdash; Cloned from a remote URL, with branch selection and sync capabilities.</li>
  <li><strong>Local Folders</strong> &mdash; Pointing to a directory on the server&rsquo;s filesystem.</li>
</ul>
<p>
  All repository data is stored under the <code>WORKSPACE_DIR</code> directory
  (default: <code>~/.roboscope/workspace</code>). Only users with the <strong>Editor</strong>
  role or above can add, edit, or delete repositories.
</p>`
      },
      {
        id: 'add-git-repo',
        title: 'Adding a Git Repository',
        content: `
<p>To add a Git repository, click the <strong>Add Repository</strong> button and fill in the form:</p>
<ol>
  <li>Select <strong>Git</strong> as the repository type.</li>
  <li>Enter the <strong>Repository URL</strong> (HTTPS or SSH). Example: <code>https://github.com/org/tests.git</code></li>
  <li>Specify the <strong>Branch</strong> to clone (default: <code>main</code>).</li>
  <li>Optionally provide a <strong>Display Name</strong>. If left blank, the repository name is inferred from the URL.</li>
  <li>Click <strong>Create</strong>.</li>
</ol>
<p>
  RoboScope uses <em>GitPython</em> to clone the repository into the workspace directory.
  The clone operation runs as a background task, so you will see a <code>pending</code>
  status until it completes. Once the clone is finished, the repository becomes available
  in the Explorer and Execution views.
</p>`,
        tip: 'For private repositories over HTTPS, include credentials in the URL or configure SSH keys on the server.'
      },
      {
        id: 'add-local-repo',
        title: 'Adding a Local Folder',
        content: `
<p>
  If your test suites already reside on the server filesystem, you can register them
  as a <strong>Local</strong> repository:
</p>
<ol>
  <li>Select <strong>Local</strong> as the repository type.</li>
  <li>Enter the absolute <strong>path</strong> to the directory containing your <code>.robot</code> files.</li>
  <li>Provide a <strong>Display Name</strong>.</li>
  <li>Click <strong>Create</strong>.</li>
</ol>
<p>
  Local repositories do not support sync or auto-sync features since they reference
  a live directory. Any changes made to the files on disk are immediately reflected
  in the Explorer.
</p>`
      },
      {
        id: 'sync-autosync',
        title: 'Sync, Save & Branches',
        content: `
<p>
  RoboScope speaks Git on your behalf — you don&rsquo;t need a Git client, but
  understanding what each button does avoids surprises.
</p>

<h4>Pulling: getting the latest from the remote</h4>
<ul>
  <li><strong>Manual Sync</strong> &mdash; Click the <strong>Sync</strong> button on a repository row. This performs a <code>git pull</code> on the configured branch and overwrites the working tree if there are no local changes blocking the merge.</li>
</ul>
<p class="rs-callout">
  <strong>Important:</strong> if you have unsaved file edits in the Explorer
  when you click <strong>Sync</strong>, the pull may either be blocked (if it
  conflicts with your edits) or silently overwrite them. Always
  <strong>save your changes to the repository</strong> first &mdash; see below.
</p>

<h4>Saving: pushing your changes back to the remote</h4>
<p>
  When you edit files in the Explorer they are written to the working tree on
  the server &mdash; not yet committed, not yet pushed. Whenever there are
  unsaved changes against the repository, the Explorer&rsquo;s file panel shows
  a coloured <strong>Save N changes</strong> button.
</p>
<ol>
  <li>Click <strong>Save N changes</strong>.</li>
  <li>Tick the files you want to publish (default: all of them).</li>
  <li>Type a one-line commit message describing what you changed.</li>
  <li>Click <strong>Save</strong>. RoboScope commits with your account&rsquo;s
      identity (your username + email become the git author / committer) and
      pushes the commit to the configured remote branch.</li>
</ol>
<p>
  If someone else pushed first and the remote moved on, the modal switches
  into a recovery state and offers a <strong>Pull latest and retry</strong>
  button. Your local commit stays in place &mdash; you cannot lose work this
  way; in the worst case you have to resolve the conflict outside RoboScope
  and push from a Git client.
</p>

<h4>Branch switching</h4>
<p>
  The branch dropdown on each project card lets you check out a different
  branch. Useful for testing feature branches or comparing results across
  branches. The dropdown does not pull &mdash; click <strong>Sync</strong>
  afterwards if you want the latest commits on the new branch.
</p>

<h4>Auto-Sync (background pull)</h4>
<p>
  The <strong>Auto-Sync</strong> toggle on a project card runs a
  <code>git pull</code> in the background every
  <code>sync_interval_minutes</code> (default 15&nbsp;min). The scheduler
  ticks every 5&nbsp;min, so very short intervals are effectively
  rounded up to 5&nbsp;min. Auto-Sync skips repos that already have a
  sync in flight, so two ticks can&rsquo;t pile on each other.
</p>
<h4>Pre-run sync (always pull before each run)</h4>
<p>
  Enable <strong>Pre-run sync</strong> on a repository when every test
  run must use the very latest commit. RoboScope will <code>git pull</code>
  synchronously right before the runner starts, with a 60&nbsp;s timeout.
  Pre-run sync is opt-in (off by default) and adds a few seconds per run;
  it composes with Auto-Sync — you can have either, both, or neither.
</p>
<p>
  If the pull fails (network error, merge conflict, timeout), the run
  still starts with whatever is on disk. The pull failure is logged and
  the next scheduled Auto-Sync will retry. The same caveat as above
  applies: always <strong>Save</strong> your changes before pulling so
  a freshly-pulled remote can&rsquo;t overwrite local edits.
</p>`,
        tip: 'Always click "Save N changes" before "Sync" — pulling first can overwrite or refuse with a merge error if you have local edits.'
      },
      {
        id: 'library-check',
        title: 'Library Check (Package Manager)',
        content: `
<p>
  The <strong>Library Check</strong> feature scans a repository's <code>.robot</code> and
  <code>.resource</code> files for <code>Library</code> imports and verifies whether the
  corresponding Python packages are installed in a selected environment.
</p>
<h4>How to Use</h4>
<ol>
  <li>On the <strong>Repositories</strong> page, click the <strong>Library Check</strong> button on any repository card.</li>
  <li>Select an <strong>Environment</strong> from the dropdown (pre-filled with the repository's default environment if set).</li>
  <li>Click <strong>Scan</strong> to analyze the repository.</li>
</ol>
<h4>Results</h4>
<p>The scan results show a table with each library and its status:</p>
<ul>
  <li><strong>Installed</strong> (green) &mdash; The library's PyPI package is installed in the environment, with the version shown.</li>
  <li><strong>Missing</strong> (red) &mdash; The library is used in test files but not installed. An <strong>Install</strong> button appears for one-click installation.</li>
  <li><strong>Built-in</strong> (gray) &mdash; The library is part of Robot Framework's standard library (e.g., Collections, String, BuiltIn) and needs no installation.</li>
</ul>
<h4>Install Missing Libraries</h4>
<p>
  Click <strong>Install</strong> next to any missing library to install it into the selected
  environment. Use <strong>Install All Missing</strong> to install all missing libraries at once.
  Installation uses the existing environment package management (pip install) and runs in the background.
</p>
<h4>Default Environment</h4>
<p>
  Each repository can have a <strong>default environment</strong> assigned. Set this when adding
  a repository or later via the repository settings. The default environment is pre-selected
  when opening the Library Check dialog.
</p>`,
        tip: 'Run a Library Check after cloning a new repository to quickly identify and install all required dependencies.'
      },
      {
        id: 'project-environment',
        title: 'Project Environment',
        content: `
<p>
  Each project can have a <strong>default environment</strong> assigned. This environment
  is used automatically when starting test runs from the project and is pre-selected
  in the Library Check dialog.
</p>
<h4>Selecting an Environment</h4>
<p>
  On the <strong>Projects</strong> page, each project card displays an environment
  dropdown. Select an environment from the list to assign it to the project. The change
  is saved immediately.
</p>
<p>
  If a system-wide default environment has been configured, it is automatically
  pre-selected when adding new projects.
</p>`,
        tip: 'Assign the correct environment to each project to avoid "missing library" errors during test execution.'
      },
      {
        id: 'bulk-operations',
        title: 'Bulk Select & Delete',
        content: `
<p>
  The Repositories page supports bulk operations for efficient management:
</p>
<ul>
  <li>Use the <strong>checkboxes</strong> on each row to select multiple repositories.</li>
  <li>A <strong>Select All</strong> checkbox in the table header toggles all items.</li>
  <li>Once selected, click the <strong>Delete Selected</strong> button (requires <strong>Editor+</strong> role).</li>
  <li>A confirmation dialog will appear listing the repositories to be removed.</li>
</ul>
<p>
  <strong>Warning:</strong> Deleting a repository removes it from RoboScope and deletes
  the cloned workspace data. Reports and run history associated with the repository
  are <em>not</em> automatically deleted. Use the Reports page to clean up old reports
  if needed.
</p>`
      }
    ]
  },

  // ─── 4. Explorer ───────────────────────────────────────────────────
  {
    id: 'explorer',
    title: 'Explorer',
    icon: '🔍',
    subsections: [
      {
        id: 'file-tree',
        title: 'File Tree Navigation',
        content: `
<p>
  The <strong>Explorer</strong> provides a file-system browser for navigating the contents
  of your repositories. The left panel displays a hierarchical tree of directories and
  files. You can:
</p>
<ul>
  <li>Expand and collapse directories by clicking the folder icon or arrow.</li>
  <li>Click a file to open it in the editor panel on the right.</li>
  <li>File icons indicate the type: <code>.robot</code> files get a special Robot Framework icon,
      while <code>.py</code>, <code>.yaml</code>, <code>.txt</code>, and other files use standard icons.</li>
  <li>The tree header shows the <strong>total number of test cases</strong> found across all <code>.robot</code> files in the project. Directories also display a badge with their individual test count.</li>
</ul>
<p>
  A <strong>repository selector</strong> dropdown at the top lets you switch between
  registered repositories without leaving the Explorer.
</p>
<h4>Localhost Features</h4>
<p>
  When accessing RoboScope on <code>localhost</code>, additional features are available:
</p>
<ul>
  <li><strong>Open Project Folder</strong> &mdash; A folder button in the tree header opens the project's root directory in your system file browser (Finder, Windows Explorer, or Nautilus).</li>
  <li><strong>Open in File Browser</strong> &mdash; Each directory in the tree has a folder button to open it directly in the system file browser.</li>
  <li><strong>Absolute Path</strong> &mdash; When a file is selected, the full filesystem path is shown below the breadcrumb.</li>
</ul>`
      },
      {
        id: 'create-rename-delete',
        title: 'Creating, Renaming & Deleting Files',
        content: `
<p>
  Users with <strong>Editor</strong> role or above can manage files directly within the Explorer:
</p>
<h4>Creating Files</h4>
<p>
  Right-click a directory in the file tree and select <strong>New File</strong> or
  <strong>New Folder</strong>. Enter the name and press Enter. New <code>.robot</code> files
  are pre-populated with a basic template including <code>*** Settings ***</code> and
  <code>*** Test Cases ***</code> sections.
</p>
<h4>Renaming</h4>
<p>
  Right-click any file or folder and select <strong>Rename</strong>. Type the new name
  and press Enter to confirm, or Escape to cancel.
</p>
<h4>Deleting</h4>
<p>
  Right-click and select <strong>Delete</strong>. A confirmation dialog will appear.
  Deleting a folder removes all its contents recursively.
</p>`,
        tip: 'Use the .resource extension for Robot Framework resource files and .robot for test suites to keep your project organized.'
      },
      {
        id: 'codemirror-editor',
        title: 'CodeMirror Editor',
        content: `
<p>
  When a file is selected, it opens in the integrated <strong>CodeMirror</strong> editor.
  Features include:
</p>
<ul>
  <li><strong>Syntax highlighting</strong> for Robot Framework (<code>.robot</code>), Python (<code>.py</code>), YAML, JSON, and XML files.</li>
  <li><strong>Line numbers</strong> displayed in the gutter.</li>
  <li><strong>Auto-indentation</strong> and bracket matching.</li>
  <li><strong>Search &amp; Replace</strong> via <code>Ctrl+F</code> / <code>Cmd+F</code>.</li>
  <li><strong>Undo/Redo</strong> with full history during the editing session.</li>
</ul>
<p>
  Changes are saved by clicking the <strong>Save</strong> button or using the keyboard
  shortcut <code>Ctrl+S</code> / <code>Cmd+S</code>. An unsaved-changes indicator
  appears in the editor tab when modifications have been made.
</p>`,
        tip: 'Use Ctrl+G (Cmd+G on Mac) to jump to a specific line number in the editor.'
      },
      {
        id: 'flow-editor',
        title: 'Visual Flow Editor',
        content: `
<p>
  For <code>.robot</code> files, the editor offers a third tab called <strong>Flow</strong>
  (alongside &ldquo;Visual Editor&rdquo; and &ldquo;Code&rdquo;). This tab renders your test cases
  as an interactive <strong>node-based graph</strong> using Vue Flow.
</p>
<h4>Node Types</h4>
<ul>
  <li><strong>Start / End Nodes</strong> &mdash; Round nodes marking the beginning and end of each flow. The Start node shows the test case / keyword name; click it to open a section-settings panel with <strong>+ [&hellip;]</strong> buttons for any setting that isn&rsquo;t already attached.</li>
  <li><strong>Keyword Nodes</strong> (blue) &mdash; Represent keyword calls. Click a node to see its arguments in the detail panel on the right.</li>
  <li><strong>Control Nodes</strong> (dashed border) &mdash; Represent control structures like <code>IF</code>, <code>FOR</code>, <code>WHILE</code>, and <code>TRY/EXCEPT</code>. Color-coded by type (amber for IF, violet for FOR/WHILE, teal for TRY, red for EXCEPT). Edge labels show branch conditions (true/false).</li>
  <li><strong>RETURN Node</strong> (green, &uarr; glyph) &mdash; Marks a keyword definition&rsquo;s return point. Each return value renders as a value chip; click the node and use the <strong>Return Values</strong> panel to add/remove cells.</li>
  <li><strong>Side notes</strong> (dashed border, italic preview) &mdash; Test-case / keyword settings rendered as &ldquo;side notes&rdquo; to the left of Start. See the next section.</li>
</ul>
<h4>Keyword Palette</h4>
<p>
  A collapsible sidebar on the left of the flow canvas provides a <strong>Keyword Palette</strong>
  with five categories: BuiltIn, Collections, String, Browser, and Control. You can:
</p>
<ul>
  <li><strong>Search</strong> &mdash; Filter keywords by name using the search box.</li>
  <li><strong>Click to Add</strong> &mdash; Click a keyword to append it as a new node.</li>
  <li><strong>Drag &amp; Drop</strong> &mdash; Drag a keyword from the palette onto the canvas to position it precisely.</li>
</ul>
<h4>Synchronization</h4>
<p>
  All three editor tabs (Visual Editor, Code, Flow) share the same underlying data model.
  Changes made in one tab are immediately reflected in the others. For example, adding a
  keyword node in the Flow tab will update both the Visual Editor form and the raw
  <code>.robot</code> code.
</p>`,
        tip: 'Use the MiniMap in the bottom-right corner of the flow canvas to navigate large test suites. The Controls panel lets you zoom in/out and fit the view.'
      },
      {
        id: 'flow-editor-settings',
        title: 'Test-case &amp; Keyword Settings (side notes)',
        content: `
<p>
  Robot Framework lets you attach <strong><code>[&hellip;]</code> settings</strong>
  to a test case (<code>[Documentation]</code>, <code>[Tags]</code>, <code>[Setup]</code>,
  <code>[Teardown]</code>, <code>[Template]</code>, <code>[Timeout]</code>) and to a
  keyword definition (the same plus <code>[Arguments]</code>). The Flow Editor
  surfaces every populated setting as its own <strong>side note</strong> stacked
  vertically to the left of the Start node, connected by a dashed edge.
</p>
<p>
  Each side note shows a label like <code>[Tags]</code> and a short italic preview
  of the value (multi-line documentation is clamped to two lines so a long
  <code>[Documentation]</code> can&rsquo;t crowd the next side note below).
  Click a side note to open a kind-aware detail panel:
</p>
<ul>
  <li><strong>[Documentation]</strong> &mdash; multi-line textarea. Multi-line
  text is preserved as <code>...</code> continuation rows in the saved
  <code>.robot</code> file.</li>
  <li><strong>[Tags]</strong> / <strong>[Arguments]</strong> &mdash; comma-
  separated input. <code>${'${name}'}=default</code> is a valid argument spec;
  <code>${'@{name}'}</code> works for varargs.</li>
  <li><strong>[Setup]</strong> / <strong>[Teardown]</strong> &mdash; keyword
  name to call before / after the body. Overrides Suite-level Test Setup /
  Teardown for this test case only.</li>
  <li><strong>[Template]</strong> (test cases only) &mdash; turns the test body
  into a data-driven loop where each row is one call to the template keyword.</li>
  <li><strong>[Timeout]</strong> &mdash; max runtime before forced abort
  (e.g. <code>30s</code>, <code>5 minutes</code>).</li>
</ul>
<h4>Adding a setting</h4>
<p>
  Click the Start node to open the <strong>Test-case settings</strong> /
  <strong>Keyword settings</strong> panel. For every kind that isn&rsquo;t
  attached yet a <strong>+ [&hellip;]</strong> button appears; click it and the
  side note shows up on the canvas with a dimmed &ldquo;click to edit&rdquo;
  placeholder, ready for input. Once every kind is filled in the panel falls
  back to a hint pointing at the side notes.
</p>
<h4>Removing a setting</h4>
<p>
  Open the side note&rsquo;s detail panel and use the <strong>&times;</strong>
  button in the header. The side note disappears from the canvas as soon as the
  underlying value clears.
</p>
<p>
  Edits are buffered locally and committed back to the form on <strong>blur</strong>
  &mdash; typing into the input no longer fires a deep watcher on every
  keystroke, so the panel survives multi-character edits intact.
</p>`,
        tip: 'A side note is just a visualisation of the underlying [Documentation] / [Tags] / etc. line — the round-trip serializer always produces the canonical .robot syntax, so a file edited in the Flow tab and saved looks identical to one written by hand.'
      },
      {
        id: 'explorer-search',
        title: 'Search',
        content: `
<p>
  The Explorer includes a <strong>search</strong> feature that lets you find files and
  content within the selected repository:
</p>
<ul>
  <li><strong>File name search</strong> &mdash; Type a file name or pattern in the search bar
      at the top of the file tree to filter the tree view.</li>
  <li><strong>Content search</strong> &mdash; Use the search panel to find text strings within
      file contents. Results show matched lines with their file path and line number.</li>
</ul>
<p>
  Clicking a search result opens the corresponding file in the editor and scrolls to
  the matching line.
</p>`
      },
      {
        id: 'run-from-explorer',
        title: 'Running Tests from Explorer',
        content: `
<p>
  Users with <strong>Runner</strong> role or above can launch test runs directly from
  the Explorer. When viewing a <code>.robot</code> file or a directory containing test files:
</p>
<ol>
  <li>Click the <strong>Run</strong> button in the editor toolbar or right-click a file/folder in the tree.</li>
  <li>The target path is automatically filled in, pointing to the selected file or directory.</li>
  <li>Optionally configure a <strong>timeout</strong> value.</li>
  <li>Click <strong>Start Run</strong> to launch the execution.</li>
</ol>
<p>
  The run status appears in real time via WebSocket. You can switch to the
  <strong>Execution</strong> page to monitor progress or continue editing while
  the tests run in the background.
</p>`,
        tip: 'Running a single .robot file is useful for quick validation, while running a directory executes the entire suite.'
      }
    ]
  },

  // ─── 5. Recorder ──────────────────────────────────────────────────
  {
    id: 'recorder',
    title: 'Recorder',
    icon: '🔴',
    subsections: [
      {
        id: 'recorder-overview',
        title: 'What is the Recorder?',
        content: `
<p>
  The <strong>RoboScope Recorder</strong> lets you capture browser interactions and
  automatically generate <code>.robot</code> test files. There are two ways to record:
</p>
<ul>
  <li><strong>Recorder v2 (recommended)</strong> &mdash; Open the launcher from the sidebar
  entry <em>Recorder</em>, or directly from the Explorer toolbar via the <em>Recorder v2</em>
  button (the Explorer button pre-selects the current repository). The launcher offers a
  transport picker (Web / Desktop&nbsp;Windows), an optional <em>Open URL</em> field so the
  controlled browser navigates straight to your starting page (only <code>http://</code> /
  <code>https://</code> URLs are accepted &mdash; leave blank to start at <code>about:blank</code>),
  and streams each captured action over Server-Sent Events into the live step list with
  per-step selector candidates.</li>
  <li><strong>Chrome Extension</strong> &mdash; Install the RoboScope Recorder extension to record
  directly in your own browser. Actions are forwarded to RoboScope via the API when connected.
  The legacy in-app Recorder button previously shown in the Explorer toolbar has been removed;
  Chrome Extension workflows are unaffected because they talk to the backend directly.</li>
</ul>
<h4>Recording Flow</h4>
<ol>
  <li>Start a recording (in-app or via extension)</li>
  <li>Interact with the web application under test</li>
  <li>Stop the recording &mdash; RoboScope generates a <code>.robot</code> file</li>
  <li>Review, edit, and save the generated test into your project</li>
</ol>`,
        tip: 'The in-app recorder works without any browser extension. The Chrome extension is useful when you need to record in a browser where you are already logged in.'
      },
      {
        id: 'recorder-anatomy',
        title: 'Generated .robot anatomy',
        content: `
<p>
  Web recordings turn into a self-contained <code>.robot</code> file with a
  <strong>variables block</strong> for the head/headless toggle plus a Browser-library
  bootstrap that's tuned for real-world pages.
</p>
<pre><code>*** Settings ***
Library           Browser

*** Variables ***
\${HEADLESS}       false

*** Test Cases ***
Recording 21
    New Browser    chromium    headless=\${HEADLESS}
    New Context
    New Page    https://example.com    wait_until=domcontentloaded
    Click    text=Sign in
    ...</code></pre>
<h4>Why <code>\${HEADLESS}</code> is a variable, not a literal</h4>
<p>
  You can flip head/headless without editing the test body — just override on the
  command line: <code>robot --variable HEADLESS:true tests/&lt;file&gt;.robot</code>. The
  default is <code>false</code> (visible browser) so re-running a recorded test
  matches the original interactive context.
</p>
<h4>Why <code>wait_until=domcontentloaded</code></h4>
<p>
  Playwright's default <code>wait_until="load"</code> waits for every subresource
  (ads, trackers, late <code>&lt;script&gt;</code> tags) to settle. On real-world
  pages that often never happens within the Browser-library 10s timeout, so the
  test fails even though the page is visibly loaded.
  <code>domcontentloaded</code> is enough: the DOM is parsed and any subsequent
  Click/Type Text/Scroll To Element finds its target.
</p>
<h4>Editing the file in the visual editor</h4>
<p>
  In the Flow editor's detail panel, a small <code>{}</code> button next to a typed
  input (checkbox / number / select) flips the slot into a free-text input — useful
  for entering a variable like <code>\${HEADLESS}</code> on a bool parameter, or for
  values the recorder couldn't infer.
</p>`
      },
      {
        id: 'recorder-selector-verification',
        title: 'Selector verification &amp; Shadow DOM',
        content: `
<p>
  Every captured action ships with a list of selector candidates &mdash;
  <code>data-testid</code>, <code>role + name</code>, <code>text</code>,
  <code>css</code> (id, class, parent-scoped), <code>xpath</code>, and a
  Shadow-DOM-aware <code>host &gt;&gt; inner</code> chain when applicable.
  RoboScope ranks them so the active candidate is the one that survives
  Playwright's strict-mode contract at replay.
</p>
<h4>Visibility-aware uniqueness</h4>
<p>
  At capture time the verifier resolves each candidate against the live
  page in a single <code>evaluate_all</code> round-trip and returns
  <code>{ total, visible, actionable }</code> counts:
</p>
<ul>
  <li><strong>actionable = 1</strong> &mdash; gold; exactly one
  visible + clickable match.</li>
  <li><strong>visible = 1</strong> &mdash; verified, light penalty
  (-5); element is visible but disabled (e.g. read-only input).</li>
  <li><strong>visible &ge; 2</strong> &mdash; multi-match; rewritten
  to a strategy-specific <code>:nth-match(1)</code> /
  <code>... &gt;&gt; nth=0</code> form so strict-mode replay still
  picks one element. Penalty -15 so a parent-context-disambiguated
  alternative outranks it whenever one exists.</li>
  <li><strong>visible = 0, total &ge; 1</strong> &mdash; element is
  hidden; kept as a desperate fallback (penalty -25) so a future
  auto-heal can try it but a visible alternative always wins.</li>
  <li><strong>total = 0</strong> &mdash; selector points at nothing,
  dropped.</li>
</ul>
<h4>Parent-context disambiguation</h4>
<p>
  A bare <code>button.submit-btn</code> matching every submit
  button on the page is the most common Playwright strict-mode
  failure at replay. The CSS strategy now also emits an ancestor-
  scoped variant whenever a stable id / data-testid exists on an
  ancestor &mdash; e.g. <code>#checkout-form button.submit-btn</code>
  &mdash; with quality bonus +10 over the bare chain. The verifier
  prefers it whenever it disambiguates.
</p>
<h4>Shadow DOM</h4>
<p>
  The capture script uses <code>ev.composedPath()[0]</code> for
  every event so a click inside an open shadow root captures the
  *real* clicked element, not the host in the light DOM. The
  ancestor walk crosses shadow boundaries via the host node, and
  each ancestor carries an <code>is_shadow_host</code> flag.
</p>
<p>
  When the captured element lives inside one or more open shadow
  roots, the synthesis emits a Playwright-chained
  <code>&lt;host-selector&gt; &gt;&gt; &lt;inner&gt;</code> candidate
  (e.g. <code>my-dialog &gt;&gt; [data-testid=&quot;save-btn&quot;]</code>).
  This pierces the shadow boundary explicitly &mdash; relying on
  Playwright's implicit piercing is engine-dependent and easy to
  misconfigure on the Browser-library / RF runner side. Closed
  shadow roots are still opaque to userspace JS, so closed-root
  elements fall back to the captured-host selector.
</p>`,
        tip: 'In the recorder UI a green ✓ indicator next to a selector means it resolves to a single visible + actionable element on the live page. Multiple candidates are shown sorted by rank — the picker lets you swap to a different one if the auto-pick does not match your intent.'
      },
      {
        id: 'recorder-extension',
        title: 'Chrome Extension',
        content: `
<p>
  The <strong>RoboScope Recorder</strong> Chrome extension records interactions directly
  in your browser &mdash; no separate browser window needed. This is especially useful
  for pages that require authentication, since you are already logged in.
</p>
<h4>Installation</h4>
<ol>
  <li>In the RoboScope repository, find the <code>extension/</code> directory</li>
  <li>Open <code>chrome://extensions</code> in Chrome or any Chromium-based browser</li>
  <li>Enable <strong>Developer mode</strong> (toggle in the top right)</li>
  <li>Click <strong>Load unpacked</strong> and select the <code>extension/</code> folder</li>
  <li>The RoboScope Recorder icon appears in your browser toolbar</li>
</ol>
<h4>Connecting to RoboScope</h4>
<ol>
  <li>Right-click the extension icon and select <strong>Options</strong></li>
  <li>Enter your RoboScope <strong>Server URL</strong> (e.g. <code>http://localhost:8000</code>)</li>
  <li>Enter an <strong>API Token</strong> (create one in RoboScope under Settings &rarr; API Tokens)</li>
  <li>Click <strong>Test Connection</strong> to verify</li>
  <li>Select the target <strong>Project</strong> from the dropdown</li>
  <li>Click <strong>Save</strong></li>
</ol>
<p>
  Once connected, a green indicator appears in the extension popup. All recorded
  actions are automatically forwarded to your RoboScope instance.
</p>`,
        tip: 'The extension also works in standalone mode without a RoboScope connection &mdash; it generates .robot files locally that you can download.'
      },
      {
        id: 'recorder-extension-usage',
        title: 'Using the Extension',
        content: `
<p>
  Click the extension icon to open the popup, then:
</p>
<ol>
  <li>Click <strong>Record</strong> to start capturing actions on the current page</li>
  <li>Interact with the page &mdash; clicks, text input, and selections are captured</li>
  <li>Click <strong>Stop</strong> to end the recording and generate the script</li>
  <li>Use <strong>Copy</strong> or <strong>Download</strong> to save the generated <code>.robot</code> file</li>
</ol>
<h4>Additional Features</h4>
<ul>
  <li><strong>Pause / Resume</strong> &mdash; Temporarily pause recording without losing captured actions</li>
  <li><strong>Scan Page</strong> &mdash; Scan the current page for all interactive elements and generate locators</li>
  <li><strong>XPath Console</strong> &mdash; Validate XPath expressions with visual highlighting on the page</li>
  <li><strong>Templates</strong> &mdash; Insert pre-built script templates (Login Flow, Form Fill, Navigation Test)</li>
  <li><strong>Settings</strong> &mdash; Choose target library (Browser / SeleniumLibrary), syntax (RPA / Testing), and language</li>
</ul>
<h4>Target Library</h4>
<table>
  <thead>
    <tr><th>Library</th><th>Keywords</th><th>Use Case</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Browser</strong></td>
      <td><code>Click</code>, <code>Fill Text</code>, <code>Select Options By</code></td>
      <td>Modern Playwright-based testing</td>
    </tr>
    <tr>
      <td><strong>SeleniumLibrary</strong></td>
      <td><code>Click Element</code>, <code>Input Text</code>, <code>Select From List By Value</code></td>
      <td>Legacy Selenium-based testing</td>
    </tr>
  </tbody>
</table>`
      }
    ]
  },

  // ─── 6. Execution ─────────────────────────────────────────────────
  {
    id: 'execution',
    title: 'Execution',
    icon: '▶️',
    subsections: [
      {
        id: 'start-run',
        title: 'Starting a New Run',
        content: `
<p>
  To start a new test run from the <strong>Execution</strong> page:
</p>
<ol>
  <li>Click the <strong>New Run</strong> button at the top of the page.</li>
  <li>Select a <strong>Repository</strong> from the dropdown.</li>
  <li>Optionally specify a <strong>Target Path</strong> &mdash; a relative path within the repository
      to restrict execution to a specific file or directory. Leave empty to run all tests.</li>
  <li>Set a <strong>Timeout</strong> in seconds (default: <code>3600</code> seconds / 1 hour).
      Runs exceeding this duration will be automatically terminated.</li>
  <li>Click <strong>Start</strong> to queue the run.</li>
</ol>
<p>
  The run enters <code>pending</code> status and is picked up by the task executor.
  Since RoboScope uses a single-worker executor, runs are processed one at a time in
  FIFO (first-in, first-out) order.
</p>
<h4>Pending activity panel</h4>
<p>
  While a run is <code>pending</code>, the run detail panel shows a small amber
  <em>Pending activity</em> box that explains <strong>why</strong> it has not started yet:
</p>
<ul>
  <li><strong>Queued behind N run(s)</strong> — one or more earlier runs still occupy the
  single executor slot. The box updates every few seconds with the current queue position.</li>
  <li><strong>Waiting for Docker image build on &lt;env&gt;</strong> — the assigned environment is
  currently building its image. The tail of the live build log is rendered inline so you
  can watch progress without leaving the run panel. The <em>Open Environments</em> link
  takes you to the full build log on the Environments page.</li>
  <li><strong>Preparing this run…</strong> — a brief transitional state that usually flips to
  <code>running</code> within seconds.</li>
</ul>`,
        tip: 'If you need to run tests from multiple repositories, queue them sequentially. They will execute in order.'
      },
      {
        id: 'run-status-table',
        title: 'Run Status Table',
        content: `
<p>
  The main Execution view shows a table of all test runs, sorted by creation date
  (newest first). Each row displays:
</p>
<table>
  <thead>
    <tr><th>Column</th><th>Description</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>ID</strong></td><td>Unique run identifier.</td></tr>
    <tr><td><strong>Repository</strong></td><td>The repository the run belongs to.</td></tr>
    <tr><td><strong>Target</strong></td><td>The file or directory targeted (or &ldquo;all&rdquo; if entire repo).</td></tr>
    <tr><td><strong>Status</strong></td><td>Color-coded badge: <code>pending</code>, <code>running</code>, <code>passed</code>, <code>failed</code>, <code>error</code>, <code>cancelled</code>, <code>timeout</code>.</td></tr>
    <tr><td><strong>Duration</strong></td><td>Elapsed time from start to completion.</td></tr>
    <tr><td><strong>Triggered by</strong></td><td>User who initiated the run.</td></tr>
    <tr><td><strong>Created</strong></td><td>Timestamp when the run was queued.</td></tr>
  </tbody>
</table>
<p>
  Status badges update <strong>in real time</strong> via WebSocket, so you never need
  to refresh the page manually.
</p>`
      },
      {
        id: 'run-details',
        title: 'Run Details & Output',
        content: `
<p>
  Click any run row to open the <strong>Run Details</strong> view, which provides:
</p>
<ul>
  <li><strong>Run metadata</strong> &mdash; Repository, target path, triggered by, timestamps, timeout, and final status.</li>
  <li><strong>Standard Output (stdout)</strong> &mdash; The Robot Framework console output, streamed live while the run is in progress.</li>
  <li><strong>Standard Error (stderr)</strong> &mdash; Any error output from the Python process, useful for diagnosing crashes or import errors.</li>
</ul>
<p>
  The output panel auto-scrolls to the bottom during active runs. You can toggle
  auto-scroll off to inspect earlier output. The output is displayed in a monospace
  font with ANSI color support stripped for readability.
</p>`
      },
      {
        id: 'cancel-retry',
        title: 'Cancel & Retry',
        content: `
<p>
  The Execution page provides several control actions:
</p>
<h4>Cancelling a Run</h4>
<p>
  Click the <strong>Cancel</strong> button on a <code>running</code> or <code>pending</code> run
  to terminate it. The underlying subprocess is actually killed (not just marked), ensuring
  resources are freed immediately. The run status changes to <code>cancelled</code>.
  Requires <strong>Runner</strong> role or above.
</p>
<h4>Retry a Run</h4>
<p>
  For runs in a terminal state (<code>failed</code>, <code>error</code>, <code>cancelled</code>,
  <code>timeout</code>), a <strong>Retry</strong> button appears. Clicking it creates a new
  run with the same configuration (repository, target, timeout) and queues it for execution.
</p>
<h4>Cancel All Runs</h4>
<p>
  The <strong>Cancel All</strong> button at the top of the Execution page terminates
  all currently <code>running</code> and <code>pending</code> runs in one action.
  This is useful when you need to free up the executor immediately. Requires
  <strong>Runner</strong> role or above.
</p>`,
        tip: 'Use "Cancel All" cautiously in multi-user environments, as it affects runs started by all users.'
      }
    ]
  },

  // ─── 6. Reports ───────────────────────────────────────────────────
  {
    id: 'reports',
    title: 'Reports',
    icon: '📋',
    subsections: [
      {
        id: 'report-list',
        title: 'Report List',
        content: `
<p>
  The <strong>Reports</strong> page displays all generated test reports. After each
  completed run, Robot Framework produces an <code>output.xml</code> file that RoboScope
  parses and stores for later analysis.
</p>
<p>Each report row shows:</p>
<ul>
  <li><strong>Report ID</strong> &mdash; Unique identifier linked to the originating run.</li>
  <li><strong>Repository</strong> &mdash; Source repository name.</li>
  <li><strong>Pass / Fail Counts</strong> &mdash; Number of passed and failed test cases, displayed as colored badges.</li>
  <li><strong>Total Tests</strong> &mdash; Total test case count.</li>
  <li><strong>Duration</strong> &mdash; Total run duration.</li>
  <li><strong>Created</strong> &mdash; Timestamp of report generation.</li>
</ul>
<p>
  Click any row to open the detailed <strong>Report Detail</strong> view.
</p>`
      },
      {
        id: 'report-detail',
        title: 'Report Detail View',
        content: `
<p>
  The Report Detail page provides three tabs for analyzing test results:
</p>
<h4>Summary Tab</h4>
<p>
  Displays KPI cards (total tests, passed, failed, duration), a table of failed tests
  with error messages, and a table of all test results with status, suite, duration, and tags.
  Clicking a test name navigates to the <strong>Test History</strong> view for that test.
</p>
<h4>Detailed Report Tab</h4>
<p>
  A rich, interactive tree view of the full test execution &mdash; similar to Robot Framework&rsquo;s
  <code>log.html</code> but integrated directly into RoboScope. It parses the <code>output.xml</code>
  and renders suites, tests, and keywords as an expandable tree hierarchy.
</p>
<p>Features of the Detailed Report tab:</p>
<ul>
  <li><strong>Toolbar</strong> &mdash; <em>Expand All</em> / <em>Collapse All</em> buttons to quickly
      open or close all tree nodes, and a <em>Status Filter</em> dropdown to show All, Passed Only,
      or Failed Only tests.</li>
  <li><strong>Suite Statistics</strong> &mdash; Each suite header shows pass/fail counts
      (e.g., &#10003; 5 &#10007; 2) alongside the duration.</li>
  <li><strong>Keyword Timestamps</strong> &mdash; Keywords display their start time in
      <code>HH:MM:SS.sss</code> format for precise timing analysis.</li>
  <li><strong>Message Log</strong> &mdash; Each keyword&rsquo;s messages are shown with timestamp,
      log level (INFO, WARN, FAIL, DEBUG), and message text. Messages are color-coded by level.</li>
  <li><strong>Inline Screenshots</strong> &mdash; Robot Framework screenshots embedded in
      messages (e.g., from SeleniumLibrary) are rendered inline with proper image display.
      Image sources are automatically resolved to the report assets endpoint.</li>
  <li><strong>Tags &amp; Arguments</strong> &mdash; Test tags are shown as colored chips, and
      keyword arguments are displayed when a keyword node is expanded.</li>
  <li><strong>Error Highlighting</strong> &mdash; Failed tests show their error message in a
      red-highlighted box for quick identification.</li>
</ul>
<h4>HTML Report Tab</h4>
<p>
  Embeds the original Robot Framework HTML report (<code>report.html</code>) in an iframe
  with a toolbar for navigation (back to Summary) and reload. This is the same report you
  would get from running <code>robot</code> on the command line, complete with interactive
  charts, keyword details, and log links.
</p>`,
        tip: 'Use the Detailed Report tab for in-depth debugging with keyword-level timing and screenshots. The Status Filter helps focus on failures quickly.'
      },
      {
        id: 'report-download',
        title: 'ZIP Download',
        content: `
<p>
  Each report can be downloaded as a <strong>ZIP archive</strong> containing all output
  files generated by Robot Framework:
</p>
<ul>
  <li><code>output.xml</code> &mdash; Machine-readable XML output.</li>
  <li><code>report.html</code> &mdash; Interactive HTML report.</li>
  <li><code>log.html</code> &mdash; Detailed execution log.</li>
  <li>Any additional artifacts (screenshots, etc.) captured during the run.</li>
</ul>
<p>
  Click the <strong>Download ZIP</strong> button on the Report Detail page. The archive
  is generated server-side and streamed to your browser.
</p>`
      },
      {
        id: 'report-bulk-delete',
        title: 'Bulk Delete Reports',
        content: `
<p>
  Over time, accumulated reports can consume significant disk space. The Reports page
  provides two deletion mechanisms:
</p>
<ul>
  <li><strong>Individual Delete</strong> &mdash; Click the delete icon on a report row to remove
      a single report (requires <strong>Editor+</strong>).</li>
  <li><strong>Delete All Reports</strong> &mdash; Click the <strong>Delete All</strong> button to
      remove every report in the system. A confirmation dialog ensures you don&rsquo;t
      accidentally wipe data. This action requires the <strong>Admin</strong> role.</li>
</ul>
<p>
  <strong>Note:</strong> Deleting reports is permanent. The associated report files are
  removed from the <code>REPORTS_DIR</code> directory on the server.
</p>`,
        tip: 'Consider downloading important reports as ZIP before performing a bulk delete.'
      },
      {
        id: 'ai-failure-analysis',
        title: 'AI Failure Analysis',
        content: `
<p>
  When a report contains failed tests, the Summary tab shows an
  <strong>AI Failure Analysis</strong> card at the bottom. This feature uses a
  configured LLM provider to automatically analyze test failures and suggest
  root causes and fixes.
</p>
<h4>Prerequisites</h4>
<ul>
  <li>At least one <strong>AI provider</strong> must be configured in
      <strong>Settings &gt; AI Providers</strong> (requires Admin role).</li>
  <li>The report must contain at least one failed test.</li>
</ul>
<h4>How to Use</h4>
<ol>
  <li>Navigate to a report with failed tests. The analysis card is available in <strong>two places</strong>:
      <ul>
        <li><strong>Reports page</strong> &mdash; click a report to open the detail view.</li>
        <li><strong>Execution page</strong> &mdash; click a completed run to expand its detail panel.</li>
      </ul>
  </li>
  <li>Scroll down to the <strong>AI Failure Analysis</strong> card in the Summary tab.</li>
  <li>Click <strong>Analyze Failures</strong>. The analysis typically takes 10&ndash;30 seconds
      depending on the number of failures and the LLM provider speed.</li>
  <li>Once complete, the analysis is displayed as formatted markdown including:
      <ul>
        <li><strong>Root Cause Analysis</strong> &mdash; per-failure diagnosis</li>
        <li><strong>Pattern Detection</strong> &mdash; common themes across failures</li>
        <li><strong>Suggested Fixes</strong> &mdash; actionable code or configuration changes</li>
        <li><strong>Priority Ranking</strong> &mdash; CRITICAL / HIGH / MEDIUM / LOW</li>
      </ul>
  </li>
</ol>
<h4>States</h4>
<ul>
  <li><strong>No provider</strong> &mdash; If no AI provider is configured, a hint message
      directs you to the Settings page.</li>
  <li><strong>Loading</strong> &mdash; A spinner is shown while the LLM processes the request.</li>
  <li><strong>Error</strong> &mdash; If the analysis fails (e.g., API rate limit), the error
      message is shown with a Retry button.</li>
  <li><strong>Completed</strong> &mdash; The analysis result is rendered with a token usage
      counter and a Re-analyze button to run a fresh analysis.</li>
</ul>
<p>
  The analysis runs as a background job and does not block other operations.
  Each analysis is an independent LLM call &mdash; re-analyzing may produce
  different results.
</p>
<h4>rf-mcp Knowledge Enrichment</h4>
<p>
  If the <strong>rf-mcp server</strong> is running (configured in Settings &gt; Robot Framework Knowledge),
  the analysis is automatically enriched with Robot Framework keyword documentation.
  The system extracts keyword names from error messages (e.g., &ldquo;No keyword with name
  &lsquo;Click Element&rsquo; found&rdquo;) and looks up their documentation via rf-mcp.
  This provides the LLM with accurate keyword signatures and usage examples, resulting
  in more precise fix suggestions.
</p>`,
        tip: 'The AI analysis works best with descriptive error messages. If your tests use custom failure messages, the LLM can provide more specific fix suggestions. Enable the rf-mcp server for even better results.'
      }
    ]
  },

  // ─── 7. Statistics ─────────────────────────────────────────────────
  {
    id: 'statistics',
    title: 'Statistics',
    icon: '📈',
    subsections: [
      {
        id: 'stats-overview',
        title: 'Statistics Overview',
        content: `
<p>
  The <strong>Statistics</strong> page offers data-driven insights into your testing
  activity over time. It combines KPI cards, trend charts, and flaky test detection
  to help you understand quality trends and identify problem areas.
</p>
<p>
  All data is accessible to any authenticated user (Viewer and above). The page
  automatically fetches fresh data when filters are changed.
</p>`
      },
      {
        id: 'stats-filters',
        title: 'Time Period & Repository Filters',
        content: `
<p>
  Two filter controls appear at the top of the Statistics page:
</p>
<h4>Time Period</h4>
<p>
  Select a pre-defined time window for all statistics:
</p>
<ul>
  <li><strong>7 days</strong> &mdash; Last week of activity.</li>
  <li><strong>14 days</strong> &mdash; Last two weeks.</li>
  <li><strong>30 days</strong> &mdash; Last month (default).</li>
  <li><strong>90 days</strong> &mdash; Last quarter.</li>
  <li><strong>1 year</strong> &mdash; Last 365 days.</li>
</ul>
<h4>Repository Filter</h4>
<p>
  Optionally select a specific repository to narrow the statistics. When set to
  <strong>All Repositories</strong>, aggregated data across all repos is shown.
</p>
<p>
  Changing either filter immediately refreshes all KPI cards, charts, and tables on the page.
</p>`
      },
      {
        id: 'stats-kpi',
        title: 'KPI Cards & Success Rate Chart',
        content: `
<p>
  The Statistics KPI cards provide a deeper view than the Dashboard:
</p>
<ul>
  <li><strong>Total Runs</strong> &mdash; Number of completed runs in the selected period.</li>
  <li><strong>Success Rate</strong> &mdash; Percentage of fully passing runs.</li>
  <li><strong>Average Duration</strong> &mdash; Mean run time.</li>
  <li><strong>Flaky Tests</strong> &mdash; Count of tests that alternate between pass and fail.</li>
</ul>
<h4>Success Rate Over Time</h4>
<p>
  A line chart shows the daily success rate for the selected period. The X-axis
  represents dates and the Y-axis shows the percentage (0&ndash;100%). This chart
  makes it easy to spot regressions or improvements over time. The chart is powered
  by <strong>Chart.js</strong> and supports hover tooltips for exact values.
</p>`,
        tip: 'A declining success rate trend often indicates new code changes introducing failures. Investigate the specific dates of drops.'
      },
      {
        id: 'pass-fail-trend',
        title: 'Pass/Fail Trend',
        content: `
<p>
  A <strong>stacked bar chart</strong> visualizes the number of passed vs. failed test
  cases per day (or per week for longer time ranges). This complements the success rate
  chart by showing absolute volumes:
</p>
<ul>
  <li><strong>Green bars</strong> represent passed test cases.</li>
  <li><strong>Red bars</strong> represent failed test cases.</li>
</ul>
<p>
  High volumes of green with occasional red spikes indicate a generally healthy test suite
  with periodic issues. Consistent red bars suggest systemic problems that need attention.
</p>`
      },
      {
        id: 'flaky-detection',
        title: 'Flaky Test Detection',
        content: `
<p>
  A <strong>flaky test</strong> is one that alternates between passing and failing without
  any code changes. RoboScope detects flaky tests by analyzing the pass/fail history of
  individual test cases over the selected time period.
</p>
<p>
  The flaky tests table shows:
</p>
<table>
  <thead>
    <tr><th>Column</th><th>Description</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>Test Name</strong></td><td>Full qualified name of the flaky test case.</td></tr>
    <tr><td><strong>Flip Count</strong></td><td>Number of times the result changed (pass&rarr;fail or fail&rarr;pass).</td></tr>
    <tr><td><strong>Pass Rate</strong></td><td>Percentage of runs where the test passed.</td></tr>
    <tr><td><strong>Last Result</strong></td><td>Most recent outcome (pass or fail badge).</td></tr>
  </tbody>
</table>
<p>
  Tests are ranked by flip count in descending order. High flip counts indicate
  unreliable tests that should be investigated for timing issues, environment
  dependencies, or non-deterministic behavior.
</p>`,
        tip: 'Flaky tests erode confidence in your test suite. Prioritize fixing tests with the highest flip counts.'
      },
      {
        id: 'stats-refresh',
        title: 'Refresh & Data Staleness',
        content: `
<p>
  Statistics data may become stale as new test runs complete. A staleness banner
  appears at the top of the Statistics page when data has not been refreshed recently.
</p>
<h4>Manual Refresh</h4>
<p>
  Click the <strong>Refresh</strong> button to reload all KPI cards, charts, and tables
  with the latest data. This re-aggregates statistics from the database for the currently
  selected filters.
</p>
<h4>Overview &amp; Deep Analysis Tabs</h4>
<p>
  The Statistics page is divided into two tabs:
</p>
<ul>
  <li><strong>Overview</strong> &mdash; KPI cards, success rate chart, pass/fail trend, and flaky test detection.</li>
  <li><strong>Deep Analysis</strong> &mdash; On-demand analysis of keyword analytics, test quality metrics, maintenance indicators, and source code analysis. Select specific KPIs and start an analysis to explore deeper insights.</li>
</ul>
<h4>Source Analysis (New)</h4>
<p>
  When a project is selected, two additional KPIs become available in the <em>Source Analysis</em> category:
</p>
<ul>
  <li><strong>Source Test Analysis</strong> &mdash; Analyses your <code>.robot</code> source files directly: test case count per file, average lines and keyword steps per test, most frequently used keywords, and a file breakdown.</li>
  <li><strong>Source Library Imports</strong> &mdash; Shows which Robot Framework libraries are imported across your <code>.robot</code> and <code>.resource</code> files, how many files use each library, and their relative distribution.</li>
</ul>
<p>
  These KPIs work independently from execution reports &mdash; they analyse the source files on disk, so you get insights even before running any tests.
</p>
<h4>Library Distribution Fix</h4>
<p>
  The <em>Library Distribution</em> KPI (in the Keyword Analytics category) now correctly resolves library names for well-known Robot Framework keywords. Previously, many keywords showed as &ldquo;Unknown&rdquo; because the <code>output.xml</code> did not always include the library attribute. The system now uses a built-in mapping of 500+ keywords to their libraries (BuiltIn, Collections, SeleniumLibrary, Browser, RequestsLibrary, etc.).
</p>`,
        tip: 'Use the Deep Analysis tab to investigate keyword durations, assertion density, and error patterns across your test suites. Select a project to enable Source Analysis KPIs.'
      }
    ]
  },

  // ─── 7.5 Self-Healing & Resilience ────────────────────────────────
  {
    id: 'self-healing',
    title: 'Self-Healing & Resilience',
    icon: '🩹',
    subsections: [
      {
        id: 'self-healing-overview',
        title: 'How self-healing works',
        content: `
<p>
  Tests drift. A dev renames <code>id=submit</code> to <code>id=submit-btn</code>,
  or wraps a button in a new <code>&lt;form&gt;</code>, and every test that referenced
  the old locator breaks. RoboScope's self-healing library retries failed
  selectors at runtime against the live DOM — the test passes while RoboScope
  records the swap for you to review.
</p>
<h4>Opt-in per keyword</h4>
<p>
  Self-healing is not automatic. You import the library and write the
  healed variant of the keyword instead of the plain Browser one:
</p>
<pre><code>*** Settings ***
Library    Browser
Library    RoboScopeHeal

*** Test Cases ***
Login Works
    New Browser    chromium
    New Page       https://app.example.com/login
    Heal Fill Text    id=user      alice
    Heal Fill Text    id=password  secret
    Heal Click        id=submit
    Get Text          .welcome-banner
</code></pre>
<h4>Three fallback tiers, in order</h4>
<ol>
  <li><strong>Sidecar lookup</strong> &mdash; if the <code>.robot</code> file has a sibling
  <code>&lt;name&gt;.rbs.json</code> from Recorder v2, RoboScope consults the ranked
  candidate list captured at record-time.</li>
  <li><strong>Strategy transposition</strong> &mdash; <code>id=submit</code> probes
  <code>[data-testid=submit]</code>, <code>text=submit</code>, <code>css=input#submit</code>,
  <code>role=button[name="submit"]</code>. Each candidate is verified against the live DOM
  via <code>Get Element Count</code> before being tried — non-unique / zero matches are dropped.</li>
  <li><strong>DOM-walk fingerprint</strong> &mdash; last resort. If the recording stored an
  element fingerprint (tag + id + testid + classes + role + text + ancestor chain),
  RoboScope scans the interactive elements on the live page and picks the best
  multi-signal similarity match above a confidence threshold.</li>
</ol>`,
        tip: 'Self-healing only fires on selector-related errors (Element not found, locator timeout). Assertion failures and other errors propagate untouched — RoboScope refuses to paper over a real regression with a silent swap.'
      },
      {
        id: 'self-healing-safety',
        title: 'Safety envelope',
        content: `
<p>
  Clicking the wrong element at runtime is worse than failing. Every heal
  operation passes through four guard rails:
</p>
<ul>
  <li><strong>Per-test budget</strong> &mdash; at most three heals per test by default.
  A test that needs more than three swaps has drifted too far; RoboScope re-raises
  the original failure instead of papering over it.</li>
  <li><strong>Confidence threshold</strong> &mdash; each candidate has a quality score
  (<code>testid</code> beats <code>aria</code> beats <code>text</code> beats raw XPath).
  Mutating keywords (<code>Heal Click</code>, <code>Heal Fill Text</code>, etc.) need
  0.7+; read-only probes (<code>Heal Get Text</code>) 0.5+.</li>
  <li><strong>Per-call retry budget</strong> &mdash; one alternative, then give up. A
  second failure is the real failure.</li>
  <li><strong>Suspect classification</strong> &mdash; after the run, heals are
  cross-referenced with each test's <code>output.xml</code> outcome. If the test passed,
  the heal is <em>confirmed</em>; if it failed, the heal is <em>suspect</em> (the swap
  may have clicked the wrong element, which is why the test still broke). Only
  confirmed heals offer an Apply-Patch button.</li>
</ul>
<h4>Escape hatch: the <code>no-heal</code> tag</h4>
<p>
  Strict-CI runs can disable healing per-test by adding the <code>no-heal</code>
  tag. The <code>Heal *</code> keywords then delegate straight to the underlying
  Browser keyword without any retry — accurate pass/fail signal for flakiness
  investigations.
</p>`,
        tip: 'Default thresholds, budgets, and the sidecar path are all configurable as Library-import arguments — no monkey-patching.'
      },
      {
        id: 'self-healing-report',
        title: 'Heal report on the run detail',
        content: `
<p>
  Every successful heal is appended to <code>&lt;output_dir&gt;/heal_audit.jsonl</code>
  with the timestamp, keyword, original selector, healed selector, confidence,
  and source (sidecar / transposition / fingerprint). The run-detail panel
  parses this file and renders a compact <strong>Self-healed selectors</strong>
  card per run.
</p>
<ul>
  <li><strong>🩹 Confirmed</strong> &mdash; the test passed after the heal. The card
  offers two actions: <em>Copy patch</em> (unified-diff to your clipboard) and
  <em>Apply patch</em> (editor+ only — writes the swap directly into the
  <code>.robot</code> file with a path-traversal guard and ambiguity check).</li>
  <li><strong>⚠️ Suspect</strong> &mdash; the test failed after the heal. The swap is
  logged but <em>no</em> patch affordance is offered. Investigate before
  accepting.</li>
</ul>
<h4>Apply-patch safety</h4>
<p>
  The <code>POST /runs/&#123;id&#125;/heal-report/&#123;idx&#125;/apply</code> endpoint
  writes the patch atomically (temp file + rename), rejects suspect /
  out-of-bounds / viewer calls, refuses to write if the original selector
  line is missing or ambiguous in the target file, and is idempotent —
  re-applying the same patch returns <code>applied: false</code>.
</p>`,
      },
      {
        id: 'self-healing-diagnosis',
        title: 'Selector diagnosis on failed runs',
        content: `
<p>
  Not every run uses <code>RoboScopeHeal</code>. For failed runs that did <em>not</em>
  heal (or failed even after healing), RoboScope still helps: it scans the run
  output for common locator-failure signatures (<em>Element '...' not found</em>,
  <em>locator(...).click: Timeout</em>, <em>waiting for selector '...'</em>) and
  looks each one up in the recording sidecar. A <strong>Selector diagnosis</strong>
  card shows the failing selector + ranked alternative candidates from the
  original recording — one click to copy, paste into your editor.
</p>`,
      },
      {
        id: 'self-healing-rate-kpi',
        title: 'Heal-rate KPI',
        content: `
<p>
  Healing is a leading indicator. A rising heal rate means the test suite is
  drifting against the app; if you do nothing, tests will start failing
  outright. The Stats overview surfaces this signal via the
  <strong>🩹 Self-healed selectors</strong> card:
</p>
<ul>
  <li>Big number: total heals in the selected time window.</li>
  <li>Sub-line: how many of the runs in that window needed any healing.</li>
  <li>Badges: confirmed vs suspect split.</li>
  <li>Sparkline: per-day heal count across the window.</li>
</ul>
<p>
  The card auto-hides when no runs occurred in the window — fresh installs stay
  visually quiet.
</p>`,
        tip: 'Watch the suspect column. One or two suspects are normal (selector drift without enough signal to heal correctly). A steady stream of suspects means the fingerprint + transposition heuristics are wrong for your codebase — file an issue.'
      },
      {
        id: 'flaky-quarantine',
        title: 'Flaky-test quarantine',
        content: `
<p>
  A test that sometimes passes and sometimes fails on the same commit is
  <em>flaky</em>. RoboScope already detects these automatically (see the
  <strong>Flaky tests</strong> table on the Statistics page), but detection alone
  isn't actionable. <strong>Quarantine</strong> is:
</p>
<h4>Marking a test quarantined</h4>
<ul>
  <li>Open <strong>Statistics</strong>, scroll to the Flaky tests table.</li>
  <li>Editor+ users see a <strong>Mute</strong> button in the Quarantine column.
  Click it &rarr; the test is recorded as quarantined for the selected
  repository.</li>
  <li>The row picks up a <strong>🔕 Quarantined</strong> badge and sorts to the top
  of the table so outstanding mutes stay visible.</li>
  <li>A corresponding audit event lands in the audit log (who muted what, when,
  why).</li>
</ul>
<h4>Runtime effect</h4>
<p>
  When a run is dispatched for a repository that has quarantine entries,
  RoboScope registers a Robot Framework listener that inspects every
  <code>start_test</code>. If the test name matches a quarantine entry, the
  listener calls <code>BuiltIn().skip()</code>. The test shows as <code>SKIP</code>
  in <code>output.xml</code> &mdash; not as <code>FAIL</code> &mdash; so CI summaries
  stop drowning in known-flaky noise.
</p>
<h4>Unquarantine</h4>
<p>
  Toggling the same button (or deleting the row via the API) removes the
  entry. No DB surgery, no config diffing.
</p>`,
        tip: 'Quarantine is always-on for rows that exist. The escape hatch for "let me see the flaky signal for this one CI run" is to unquarantine the specific rows before the run and re-quarantine after. A per-run opt-out flag is deferred to a future story.'
      },
      {
        id: 'self-healing-ai-patches',
        title: 'AI-generated patch suggestions',
        content: `
<p>
  When you run <strong>Analyze failures</strong> on a report, the LLM is
  asked to emit unified-diff patches alongside the prose root-cause
  analysis wherever the fix is concrete enough. A second section
  &mdash; <strong>Suggested patches</strong> &mdash; appears below the markdown
  analysis with a per-file diff preview and a <em>Copy patch</em> button.
</p>
<p>
  These patches are <em>suggestions</em> &mdash; never auto-applied. The
  RoboScope app will not modify your repository unless you copy+paste the
  diff yourself (or use the similar Apply-patch affordance that
  <strong>confirmed</strong> runtime heals offer).
</p>`,
        tip: 'Ambiguous failures (flaky timing, infrastructure issues) never produce a patch block — the prompt explicitly instructs the LLM to stay with prose in those cases.'
      },
    ],
  },

  // ─── 8. Environments ──────────────────────────────────────────────
  {
    id: 'environments',
    title: 'Environments',
    icon: '⚙️',
    subsections: [
      {
        id: 'env-overview',
        title: 'Environment Management',
        content: `
<p>
  The <strong>Environments</strong> page lets you create and manage isolated Python
  virtual environments for test execution. Each environment can have its own set of
  installed packages and environment variables, allowing you to run tests against
  different configurations without conflicts.
</p>
<p>
  Environments are stored under the <code>VENVS_DIR</code> directory
  (default: <code>~/.roboscope/venvs</code>). Managing environments requires the
  <strong>Editor</strong> role or above.
</p>`
      },
      {
        id: 'create-venv',
        title: 'Creating a Virtual Environment',
        content: `
<p>
  To create a new Python virtual environment:
</p>
<ol>
  <li>Click <strong>New Environment</strong> on the Environments page.</li>
  <li>Enter a <strong>Name</strong> for the environment (e.g., <code>rf7-selenium</code>).</li>
  <li>Optionally provide a <strong>Description</strong> of what this environment is for.</li>
  <li>Click <strong>Create</strong>.</li>
</ol>
<p>
  RoboScope creates a Python <code>venv</code> in the background using the system Python.
  The creation process typically takes a few seconds. Once ready, the environment
  status changes from <code>creating</code> to <code>ready</code>.
</p>
<p>
  Each environment automatically includes <code>pip</code> and <code>setuptools</code>.
  You will then need to install Robot Framework and any required libraries.
</p>`,
        tip: 'Name environments descriptively, e.g., "rf7-browser" or "rf6-selenium", so team members know which libraries are included.'
      },
      {
        id: 'install-packages',
        title: 'Installing Packages',
        content: `
<p>
  After creating an environment, you can install Python packages in two ways:
</p>
<h4>Popular Robot Framework Libraries</h4>
<p>
  A curated list of commonly used packages is available for one-click installation:
</p>
<ul>
  <li><code>robotframework</code> &mdash; The core Robot Framework.</li>
  <li><code>robotframework-seleniumlibrary</code> &mdash; Selenium-based browser testing.</li>
  <li><code>robotframework-browser</code> &mdash; Playwright-based browser testing (requires Node.js + <code>rfbrowser init</code>).</li>
  <li><code>robotframework-browser-batteries</code> &mdash; Playwright-based browser testing, self-contained (no Node.js needed, recommended).</li>
  <li><code>robotframework-requests</code> &mdash; HTTP API testing.</li>
  <li><code>robotframework-databaselibrary</code> &mdash; Database testing.</li>
  <li><code>robotframework-sshlibrary</code> &mdash; SSH connections.</li>
  <li><code>robotframework-excellibrary</code> &mdash; Excel file handling.</li>
</ul>
<p>
  <strong>Note:</strong> Only one Browser library variant can be installed at a time.
  If you try to install <code>robotframework-browser</code> while <code>robotframework-browser-batteries</code>
  is already installed (or vice versa), you will be asked to uninstall the other variant first.
</p>
<h4>Browser Library Init Status</h4>
<p>
  When <code>robotframework-browser</code> (standard) is installed, it requires an additional
  initialization step (<code>rfbrowser init</code>) to download Playwright browsers. RoboScope
  shows the init status next to the package:
</p>
<ul>
  <li>&#x2705; <strong>Browser initialized</strong> &mdash; <code>rfbrowser init</code> was run successfully.</li>
  <li>&#x26A0;&#xFE0F; <strong>rfbrowser init required</strong> &mdash; Browsers not yet downloaded. Click the <strong>Run rfbrowser init</strong> button to trigger initialization.</li>
</ul>
<p>
  The <code>robotframework-browser-batteries</code> variant always shows &#x2705; since it is self-contained.
</p>
<h4>PyPI Search</h4>
<p>
  For any other package, use the <strong>search field</strong> to find packages on PyPI.
  Enter a package name, select the desired version, and click <strong>Install</strong>.
  The installation runs as a background task and the package list updates when complete.
</p>
<p>
  Installed packages are shown in a table with their name, version, and a
  <strong>Uninstall</strong> button.
</p>`,
        tip: 'For browser testing, use robotframework-browser-batteries to avoid Node.js setup. Only choose robotframework-browser if you need a specific Playwright version.'
      },
      {
        id: 'env-variables',
        title: 'Environment Variables',
        content: `
<p>
  Each environment can define <strong>environment variables</strong> that are injected
  into the process when tests are executed. This is useful for:
</p>
<ul>
  <li>Setting <code>BROWSER</code> to control which browser Selenium uses.</li>
  <li>Providing <code>BASE_URL</code> for application-under-test configuration.</li>
  <li>Storing <code>API_KEY</code> or other credentials without hardcoding them in test files.</li>
</ul>
<p>
  To manage variables, navigate to an environment&rsquo;s detail page and use the
  <strong>Variables</strong> tab. Each variable has a <strong>Key</strong> and
  <strong>Value</strong>. Click <strong>Add Variable</strong> to create a new entry,
  or use the edit/delete icons to modify existing ones.
</p>`,
        tip: 'Avoid storing highly sensitive credentials as environment variables. Consider using a secrets manager for production deployments.'
      },
      {
        id: 'docker-build',
        title: 'Docker Build & Image Staleness',
        content: `
<h4>Docker Build Terminal</h4>
<p>
  When building a Docker image for an environment, RoboScope streams the build output
  live to a <strong>terminal component</strong> in the UI. The terminal features a pulsing
  dot indicator during active builds, auto-scroll to follow new output, and a
  show/hide toggle to collapse the terminal when not needed.
</p>
<h4>Image Staleness Detection</h4>
<p>
  After installing or removing packages, the Docker image may become outdated. RoboScope
  tracks when packages were last changed (<code>packages_changed_at</code>) and when
  the image was last built (<code>docker_image_built_at</code>). If packages have changed
  since the last build, an <strong>amber warning banner</strong> appears in the Execution
  and Explorer views, prompting you to rebuild the image.
</p>
<p>
  Click the <strong>Rebuild</strong> button to start a new Docker build that incorporates
  the latest package changes.
</p>
<h4>Browser Library Initialization</h4>
<p>
  When using <code>robotframework-browser</code>, RoboScope automatically checks whether
  the Browser library's <code>node_modules</code> are properly initialized after installation.
  If initialization is needed, a status indicator shows <strong>initializing</strong> in the UI,
  and a pre-run check ensures the Browser library is ready before test execution begins.
</p>`
      },
      {
        id: 'clone-delete-env',
        title: 'Cloning & Deleting Environments',
        content: `
<p>
  To save time when setting up similar environments:
</p>
<h4>Clone</h4>
<p>
  Click the <strong>Clone</strong> button on an existing environment. This creates a
  new environment with the same installed packages and environment variables. You will
  be prompted to provide a new name. Cloning is useful when you need a slight variation
  of an existing setup (e.g., testing with a different Robot Framework version).
</p>
<h4>Delete</h4>
<p>
  Click the <strong>Delete</strong> button and confirm the dialog to permanently remove
  an environment. This deletes the virtual environment directory and all associated
  configuration. Runs that were configured to use a deleted environment will need to
  be updated to use a different one.
</p>`
      }
    ]
  },

  // ─── 9. Settings ──────────────────────────────────────────────────
  {
    id: 'settings',
    title: 'Settings',
    icon: '🔧',
    subsections: [
      {
        id: 'settings-overview',
        title: 'Settings Overview',
        content: `
<p>
  The <strong>Settings</strong> page is accessible only to users with the
  <strong>Admin</strong> role. It provides user management capabilities and
  application-wide configuration options.
</p>
<p>
  Non-admin users will not see the Settings entry in the sidebar navigation.
  Attempting to access the settings URL directly with insufficient permissions
  results in a redirect to the Dashboard.
</p>`
      },
      {
        id: 'user-management',
        title: 'User Management',
        content: `
<p>
  The user management section displays a table of all registered users with the
  following columns:
</p>
<ul>
  <li><strong>Email</strong> &mdash; The user&rsquo;s login email address.</li>
  <li><strong>Name</strong> &mdash; Display name shown in the header and run history.</li>
  <li><strong>Role</strong> &mdash; Current role assignment (Viewer, Runner, Editor, Admin).</li>
  <li><strong>Status</strong> &mdash; Active or inactive badge.</li>
  <li><strong>Created</strong> &mdash; Account creation date.</li>
  <li><strong>Actions</strong> &mdash; Edit and delete buttons.</li>
</ul>
<h4>Creating a User</h4>
<p>
  Click <strong>Add User</strong> and fill in the form:
</p>
<ol>
  <li>Enter the <strong>Email</strong> (must be unique).</li>
  <li>Enter a <strong>Display Name</strong>.</li>
  <li>Set the initial <strong>Password</strong> (minimum 6 characters).</li>
  <li>Assign a <strong>Role</strong>.</li>
  <li>Click <strong>Create</strong>.</li>
</ol>
<p>
  The new user can immediately log in with the provided credentials.
</p>`
      },
      {
        id: 'role-assignment',
        title: 'Role Assignment',
        content: `
<p>
  To change a user&rsquo;s role, click the <strong>Edit</strong> button on their row.
  In the edit dialog, select the new role from the dropdown and save.
</p>
<p>
  Role changes take effect on the user&rsquo;s next API request. If the user is
  currently logged in, their JWT token still contains the old role until it is
  refreshed. For immediate effect, the user should log out and log back in.
</p>
<h4>Role Assignment Guidelines</h4>
<table>
  <thead>
    <tr><th>Role</th><th>Best For</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>Viewer</strong></td><td>Stakeholders, managers, and team members who only need to review results.</td></tr>
    <tr><td><strong>Runner</strong></td><td>QA engineers who need to trigger test runs but not modify test code.</td></tr>
    <tr><td><strong>Editor</strong></td><td>Test developers who write and maintain Robot Framework tests.</td></tr>
    <tr><td><strong>Admin</strong></td><td>System administrators responsible for user management and configuration.</td></tr>
  </tbody>
</table>`,
        tip: 'Follow the principle of least privilege: assign the minimum role needed for each user\'s responsibilities.'
      },
      {
        id: 'activate-deactivate',
        title: 'Activate & Deactivate Users',
        content: `
<p>
  Instead of deleting a user, you can <strong>deactivate</strong> their account:
</p>
<ul>
  <li>Click the <strong>Edit</strong> button on the user row.</li>
  <li>Toggle the <strong>Active</strong> switch to off.</li>
  <li>Save the changes.</li>
</ul>
<p>
  Deactivated users cannot log in and their existing JWT tokens are rejected.
  However, their run history and associated data are preserved. To restore access,
  simply toggle the Active switch back on.
</p>
<p>
  <strong>Deleting</strong> a user permanently removes their account. Use the
  <strong>Delete</strong> button and confirm the dialog. This action cannot be undone.
</p>`,
        tip: 'Prefer deactivation over deletion for users who may return. This preserves their historical activity data.'
      },
      {
        id: 'password-reset',
        title: 'Password Reset',
        content: `
<p>
  Admins can reset any user&rsquo;s password directly from the Users tab:
</p>
<ol>
  <li>Navigate to <strong>Settings &gt; Users</strong>.</li>
  <li>Click the <strong>Reset Password</strong> button on the user&rsquo;s row.</li>
  <li>Enter the new password (minimum 6 characters) in the dialog.</li>
  <li>Click <strong>Set Password</strong>.</li>
</ol>
<p>
  The password change takes effect immediately. The user&rsquo;s existing sessions
  remain valid, but they will need the new password for their next login.
</p>`,
        tip: 'Communicate the new password to the user through a secure channel. Consider asking them to change it again on first login.'
      },
      {
        id: 'api-tokens',
        title: 'API Tokens',
        content: `
<p>
  The <strong>API Tokens</strong> tab in Settings allows administrators to create tokens for
  CI/CD pipelines and service accounts. Tokens provide programmatic access to the RoboScope API
  without requiring interactive login.
</p>
<h4>Creating a Token</h4>
<ol>
  <li>Navigate to <strong>Settings &gt; API Tokens</strong>.</li>
  <li>Click <strong>Create Token</strong>.</li>
  <li>Enter a <strong>name</strong> (e.g., &ldquo;Jenkins Pipeline&rdquo;).</li>
  <li>Select a <strong>role</strong> &mdash; either <em>Runner</em> (can trigger runs) or <em>Editor</em> (can also modify files and settings).</li>
  <li>Optionally set an <strong>expiry date</strong>. Tokens without an expiry remain valid until revoked.</li>
  <li>Click <strong>Create</strong>. The token is displayed once &mdash; copy it immediately.</li>
</ol>
<h4>Using a Token</h4>
<p>
  Include the token in the <code>Authorization</code> header of your HTTP requests:
</p>
<p><code>Authorization: Bearer rbs_...</code></p>
<p>
  All tokens use the <code>rbs_</code> prefix for easy identification. The token value is
  stored as a SHA-256 hash in the database &mdash; it cannot be recovered after creation.
</p>
<h4>Revoking a Token</h4>
<p>
  Click the <strong>Revoke</strong> button next to any token to immediately invalidate it.
  Revoked tokens cannot be restored.
</p>`,
        tip: 'Use short-lived tokens with expiry dates for CI/CD pipelines to reduce security risk. Create separate tokens for each pipeline or service.'
      },
      {
        id: 'outbound-webhooks',
        title: 'Outbound Webhooks',
        content: `
<p>
  The <strong>Webhooks</strong> tab in Settings lets you configure outbound HTTP notifications
  that are sent whenever test run events occur. This is useful for integrating RoboScope with
  chat tools (Slack, Teams), monitoring systems, or custom dashboards.
</p>
<h4>Creating a Webhook</h4>
<ol>
  <li>Navigate to <strong>Settings &gt; Webhooks</strong>.</li>
  <li>Click <strong>Add Webhook</strong>.</li>
  <li>Enter the <strong>target URL</strong> (must be HTTPS for production use).</li>
  <li>Enter an optional <strong>secret</strong> for HMAC-SHA256 payload signing.</li>
  <li>Select the <strong>events</strong> you want to subscribe to:
    <code>run.started</code>, <code>run.passed</code>, <code>run.failed</code>,
    <code>run.error</code>, <code>run.cancelled</code>, <code>run.timeout</code>.
  </li>
  <li>Click <strong>Save</strong>.</li>
</ol>
<h4>Payload Signatures</h4>
<p>
  If a secret is configured, each delivery includes an <code>X-RoboScope-Signature</code> header
  containing an HMAC-SHA256 signature of the request body. Verify this signature on the receiving
  end to ensure the payload was sent by RoboScope and has not been tampered with.
</p>
<h4>Delivery Log &amp; Retries</h4>
<p>
  RoboScope keeps a delivery log for each webhook showing status codes, timestamps, and response
  bodies. Failed deliveries are retried up to 3 times with exponential backoff. Use the
  <strong>Test Ping</strong> button to verify connectivity before relying on the webhook.
</p>`,
        tip: 'Use the Test Ping button after creating a webhook to verify that your endpoint receives payloads correctly before waiting for a real run event.'
      },
      {
        id: 'git-webhook-trigger',
        title: 'Git Webhook Trigger',
        content: `
<p>
  RoboScope can automatically trigger test runs when code is pushed to a Git repository.
  The <strong>Webhooks</strong> tab in Settings displays an <strong>inbound webhook URL</strong>
  that you can configure in your GitHub or GitLab repository settings.
</p>
<h4>Setup</h4>
<ol>
  <li>Copy the inbound webhook URL from <strong>Settings &gt; Webhooks</strong>.</li>
  <li>In your Git hosting platform (GitHub or GitLab), go to your repository&rsquo;s webhook settings.</li>
  <li>Add the RoboScope URL as a new webhook.</li>
  <li>Select <strong>Push events</strong> as the trigger.</li>
  <li>Save the webhook configuration.</li>
</ol>
<h4>How It Works</h4>
<p>
  When a push event is received, RoboScope matches the incoming <code>git_url</code> against
  configured projects (with or without <code>.git</code> suffix). It extracts the branch name
  from the <code>refs/heads/...</code> reference and automatically creates an
  <code>ExecutionRun</code> for the matched project on the pushed branch.
</p>`,
        tip: 'Make sure your RoboScope instance is reachable from your Git hosting platform. For GitHub, the webhook URL must be publicly accessible or use a tunnel for local development.'
      },
      {
        id: 'audit-log',
        title: 'Audit Log',
        content: `
<p>
  The <strong>Audit Log</strong> tab in Settings provides a comprehensive record of all
  write operations (POST, PUT, PATCH, DELETE) performed in RoboScope. This is essential
  for compliance, security monitoring, and debugging.
</p>
<h4>What Is Logged</h4>
<p>
  Each audit log entry captures:
</p>
<ul>
  <li><strong>Timestamp</strong> &mdash; When the action occurred.</li>
  <li><strong>User</strong> &mdash; Who performed the action (username).</li>
  <li><strong>Action</strong> &mdash; The HTTP method and endpoint (e.g., POST /runs).</li>
  <li><strong>Resource</strong> &mdash; The type and ID of the affected resource.</li>
  <li><strong>IP Address</strong> &mdash; The client IP address.</li>
  <li><strong>Details</strong> &mdash; Additional context stored as JSON (e.g., changed fields).</li>
</ul>
<h4>Filtering &amp; Export</h4>
<p>
  Use the filter controls to narrow down entries by action type, resource type, or user.
  The paginated table supports navigating through large log volumes. Click
  <strong>Export CSV</strong> to download the filtered log entries for external analysis or
  archival purposes.
</p>
<h4>Retention Enforcement</h4>
<p>
  A background scheduler runs every 24 hours to enforce retention policies. Reports and runs
  older than the configured <code>report_retention_days</code> setting are automatically deleted.
  Administrators can also trigger retention enforcement manually via
  <strong>Settings &gt; Audit Log &gt; Run Retention</strong>.
</p>`,
        tip: 'Export audit logs regularly for compliance purposes. The CSV export includes all fields and respects any active filters.'
      },
      {
        id: 'secrets-encryption',
        title: 'Secrets Encryption',
        content: `
<p>
  Environment variables can be marked as <strong>secret</strong> to protect sensitive values
  such as API keys, passwords, and tokens. Secret variables are encrypted at rest using
  Fernet symmetric encryption, derived from the application&rsquo;s <code>SECRET_KEY</code>.
</p>
<h4>Marking a Variable as Secret</h4>
<ol>
  <li>Navigate to <strong>Environments</strong> and select an environment.</li>
  <li>In the <strong>Variables</strong> section, add or edit a variable.</li>
  <li>Toggle the <strong>Secret</strong> switch to enable encryption.</li>
  <li>Save the variable. The value is encrypted immediately.</li>
</ol>
<h4>How It Works</h4>
<ul>
  <li>Secret values are stored as encrypted ciphertext in the database.</li>
  <li>The UI displays secret values as <code>********</code> &mdash; they cannot be read back.</li>
  <li>Values are decrypted only at test execution time, when they are injected into the
      test runner&rsquo;s environment.</li>
  <li>Legacy plaintext secrets (created before encryption was enabled) continue to work
      through graceful fallback.</li>
</ul>`,
        tip: 'Always use a strong, unique SECRET_KEY in production. If the SECRET_KEY changes, previously encrypted secrets will become unreadable.'
      },
      {
        id: 'identity-providers',
        title: 'Identity Providers (SSO)',
        content: `
<p>
  RoboScope supports <strong>Single Sign-On (SSO)</strong> via OpenID Connect (OIDC).
  Once an identity provider is configured and enabled, a corresponding
  <strong>Sign in with &hellip;</strong> button appears on the login screen and your
  users no longer need a separate RoboScope password.
</p>
<p>
  Supported provider types:
</p>
<ul>
  <li><strong>Azure AD / Microsoft Entra ID</strong></li>
  <li><strong>Google Workspace</strong></li>
  <li><strong>GitHub</strong></li>
  <li><strong>Generic OIDC</strong> &mdash; any standards-compliant OIDC issuer
      (Okta, Keycloak, Auth0, Authentik, &hellip;)</li>
</ul>

<h4>1. Prepare the application at your IdP</h4>
<p>
  In your IdP&rsquo;s admin console, register a new web application and note the
  <strong>Client ID</strong> and <strong>Client Secret</strong>. Set the
  <strong>Redirect URI</strong> to:
</p>
<p><code>https://&lt;your-roboscope-host&gt;/auth/sso/callback</code></p>
<p>
  RoboScope shows the exact URL on the configuration form (with a copy button).
  The application must be allowed to request the scopes
  <code>openid profile email</code> at minimum. If you want group-based team
  assignment, also enable a <strong>groups</strong> claim
  (Azure AD: <em>Token configuration</em> &rarr; add <em>groups</em> claim;
  Keycloak: add a <em>group membership</em> mapper).
</p>

<h4>2. Create the provider in RoboScope</h4>
<ol>
  <li>Open <strong>Admin &gt; Identity Providers</strong> in the sidebar.</li>
  <li>Click <strong>Add Provider</strong>.</li>
  <li>Fill in the form:
    <ul>
      <li><strong>Name</strong> &mdash; label shown on the login button (e.g. &ldquo;Company SSO&rdquo;).</li>
      <li><strong>Provider Type</strong> &mdash; one of the four types above.</li>
      <li><strong>Issuer URL</strong> &mdash; the OIDC issuer / discovery base URL.
          Examples:
        <ul>
          <li>Azure AD: <code>https://login.microsoftonline.com/&lt;tenant-id&gt;/v2.0</code></li>
          <li>Google: <code>https://accounts.google.com</code></li>
          <li>GitHub: <code>https://token.actions.githubusercontent.com</code> or your OIDC proxy</li>
          <li>Generic: the URL where <code>/.well-known/openid-configuration</code> is served</li>
        </ul>
      </li>
      <li><strong>Client ID</strong> &mdash; from the IdP application.</li>
      <li><strong>Client Secret</strong> &mdash; from the IdP application. Stored encrypted at rest (Fernet).</li>
      <li><strong>Scopes</strong> &mdash; default <code>openid profile email</code>; add more (e.g. <code>groups</code>, <code>offline_access</code>) as chips.</li>
      <li><strong>Group claim name</strong> &mdash; the JWT claim that holds the user&rsquo;s groups (default <code>groups</code>).</li>
    </ul>
  </li>
</ol>

<h4>3. Run the Dry-Run probe</h4>
<p>
  Before the provider can be saved, click <strong>Run Dry-Run</strong>. The probe
  fetches the OIDC discovery document, validates the JWKS endpoint, the
  configured scopes, and the group claim name. The result is shown inline:
</p>
<ul>
  <li><strong>Passed</strong> &mdash; the <strong>Save</strong> button is unlocked.</li>
  <li><strong>Failed</strong> &mdash; expand the row to see which check failed
      (most common: wrong issuer URL, blocked outbound network, scope not
      whitelisted at the IdP).</li>
</ul>
<p>
  Editing any field after a successful dry-run marks the probe as
  <em>stale</em> &mdash; you must re-run it before saving.
</p>

<h4>4. Hand-off artifact</h4>
<p>
  After the first save you can download a <strong>PDF or Markdown handoff</strong>
  from the provider edit page. The artifact lists everything the IdP admin needs
  (Redirect URI, required scopes, group claim) and is generated in the same
  language as the UI &mdash; useful when RoboScope and IdP are managed by
  different teams.
</p>

<h4>5. First user sign-in</h4>
<p>
  Once the provider is enabled, the login page shows a
  <strong>Sign in with <em>&lt;Name&gt;</em></strong> button. On first SSO login a
  RoboScope user account is created automatically and linked to the IdP subject.
  If a local password account already exists for the same email, the user is
  asked to confirm linking (consent screen).
</p>

<h4>Group-to-Team mapping</h4>
<p>
  Under <strong>Admin &gt; Teams</strong> you can map IdP group names to
  RoboScope teams. On every SSO login the user&rsquo;s team membership is
  re-synchronised from the configured group claim. Use
  <strong>Bulk-create teams from IdP groups</strong> on the Teams page to
  bootstrap mappings from groups already observed during recent logins.
</p>

<h4>Discovery cache</h4>
<p>
  OIDC discovery documents are cached for 24&nbsp;h to keep logins fast and
  resilient to short IdP outages. The provider list shows a
  <strong>stale-cache badge</strong> when the cache is older than 24&nbsp;h.
  Trigger a manual refresh from the provider list page.
</p>

<h4>Emergency bypass</h4>
<p>
  If your IdP is unreachable, an admin can still log in with the local
  <code>admin@roboscope.local</code> account (or any other local password
  account) via the <strong>Use password instead</strong> link on the login page.
  This link can be hidden under <strong>Settings &gt; Security &gt; Hide
  password form</strong> once SSO is fully rolled out.
</p>`,
        tip: 'Always run the Dry-Run probe before saving and before rolling out to users. The check catches 90% of misconfigurations (wrong issuer, missing scope, unreachable JWKS) without affecting end users.'
      }
    ]
  },

  // ─── 10. AI & Generation ──────────────────────────────────────────
  {
    id: 'ai-generation',
    title: 'AI & Generation',
    icon: '🤖',
    subsections: [
      {
        id: 'ai-overview',
        title: 'Overview',
        content: `
<p>
  RoboScope integrates with <strong>Large Language Models (LLMs)</strong> to provide
  AI-powered features for Robot Framework test development:
</p>
<ul>
  <li><strong>Spec-to-Robot Generation</strong> &mdash; Write a <code>.roboscope</code> YAML specification
      and let the LLM generate a complete <code>.robot</code> test file from it.</li>
  <li><strong>Robot-to-Spec Extraction</strong> &mdash; Reverse-engineer a <code>.roboscope</code>
      specification from an existing <code>.robot</code> file.</li>
  <li><strong>AI Failure Analysis</strong> &mdash; Automatically analyze test failures in reports
      to identify root causes and suggest fixes.</li>
  <li><strong>Drift Detection</strong> &mdash; Detect when a <code>.robot</code> file has been
      manually modified after generation, so you can re-generate from the updated spec.</li>
</ul>
<p>
  All AI features require at least one <strong>LLM provider</strong> to be configured in
  <strong>Settings &gt; AI &amp; Generation</strong>.
</p>`
      },
      {
        id: 'ai-providers',
        title: 'Configuring LLM Providers',
        content: `
<p>
  Navigate to <strong>Settings &gt; AI &amp; Generation</strong> (Admin role required)
  and click <strong>Add Provider</strong>. RoboScope supports four provider types:
</p>
<table>
  <thead>
    <tr><th>Provider</th><th>API Key</th><th>Base URL</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>OpenAI</strong></td>
      <td>Required (<code>sk-...</code>)</td>
      <td>Auto (api.openai.com)</td>
      <td>GPT-4.1, GPT-4o, o3, o4-mini</td>
    </tr>
    <tr>
      <td><strong>Anthropic</strong></td>
      <td>Required</td>
      <td>Auto (api.anthropic.com)</td>
      <td>Claude Sonnet/Opus 4.6, Haiku 4.5</td>
    </tr>
    <tr>
      <td><strong>OpenRouter</strong></td>
      <td>Required</td>
      <td>Auto (openrouter.ai)</td>
      <td>Access to 100+ models from various providers</td>
    </tr>
    <tr>
      <td><strong>Ollama (Local)</strong></td>
      <td>Not needed</td>
      <td>Auto (localhost:11434)</td>
      <td>Free, private, runs on your machine</td>
    </tr>
  </tbody>
</table>
<p>
  You can add multiple providers and set one as the <strong>default</strong>.
  The model field accepts both suggested models and custom model names (type any
  model name your provider supports).
</p>`
      },
      {
        id: 'ai-ollama-setup',
        title: 'Setting Up Ollama (Local LLM)',
        content: `
<p>
  <strong>Ollama</strong> lets you run LLMs locally on your machine for free, with
  complete privacy &mdash; no data leaves your computer. To set it up:
</p>
<ol>
  <li><strong>Install Ollama</strong> &mdash; Download from
      <code>ollama.com</code> and install it. On macOS it runs as a menu bar app,
      on Linux as a system service.</li>
  <li><strong>Pull a model</strong> &mdash; Open a terminal and run:<br />
      <code>ollama pull mistral</code><br />
      Other popular models: <code>llama3.3</code>, <code>deepseek-r1</code>,
      <code>dolphin-mistral</code>, <code>codellama</code>, <code>qwen3</code>.
      Larger models produce better results but require more RAM.</li>
  <li><strong>Verify it&rsquo;s running</strong> &mdash; Run <code>ollama list</code> to see
      your installed models. The Ollama API should be accessible at
      <code>http://localhost:11434</code>.</li>
  <li><strong>Add provider in RoboScope</strong> &mdash; Go to Settings &gt; AI &amp; Generation,
      click Add Provider:
      <ul>
        <li><strong>Provider Type:</strong> Ollama (Local)</li>
        <li><strong>Model:</strong> Type the exact model name from <code>ollama list</code>
            (e.g., <code>mistral:latest</code> or <code>dolphin-mistral:latest</code>)</li>
        <li><strong>API Key:</strong> Leave empty (disabled automatically)</li>
        <li><strong>Base URL:</strong> Leave empty for default (<code>http://localhost:11434</code>),
            or enter a custom URL if Ollama runs on a different host/port</li>
        <li>Check <strong>Set as default</strong> if this is your only provider</li>
      </ul>
  </li>
</ol>
<h4>Troubleshooting</h4>
<ul>
  <li><strong>&ldquo;model not found&rdquo;</strong> &mdash; The model name in RoboScope must
      exactly match what <code>ollama list</code> shows (including the <code>:latest</code> tag
      if applicable).</li>
  <li><strong>Connection refused</strong> &mdash; Make sure the Ollama application is running.
      On macOS check the menu bar icon; on Linux run <code>systemctl status ollama</code>.</li>
  <li><strong>Slow generation</strong> &mdash; Local models are slower than cloud APIs,
      especially on machines without a GPU. Generation can take 30&ndash;120 seconds
      for complex specifications.</li>
</ul>`,
        tip: 'For best results with code generation, use models with at least 7B parameters (e.g., mistral, llama3.1). Smaller models may produce incomplete or incorrect Robot Framework syntax.'
      },
      {
        id: 'ai-spec-generation',
        title: 'Generating Tests from Specifications',
        content: `
<p>
  The <code>.roboscope</code> format is a YAML-based test specification that describes
  tests in natural language. The LLM translates these into executable
  <code>.robot</code> files.
</p>
<h4>Workflow</h4>
<ol>
  <li>In the <strong>Explorer</strong>, create or open a <code>.roboscope</code> file.
      Use the <strong>Visual Editor</strong> tab to fill in metadata, libraries,
      test sets, and test cases, or edit the YAML directly.</li>
  <li>Click <strong>Generate</strong> in the toolbar.</li>
  <li>Select an LLM provider (or use the default) and click <strong>Generate</strong>.</li>
  <li>Review the generated <code>.robot</code> code in the <strong>Diff Preview</strong>.</li>
  <li>Click <strong>Accept &amp; Write File</strong> to save, or <strong>Discard</strong>
      to reject the result.</li>
</ol>
<p>
  After accepting, RoboScope stores a generation hash for drift detection.
  If you later edit the <code>.robot</code> file manually, the drift indicator
  warns you that it has diverged from the specification.
</p>`
      },
      {
        id: 'ai-reverse-extract',
        title: 'Extracting Specifications from Robot Files',
        content: `
<p>
  For existing <code>.robot</code> files that don&rsquo;t have a specification yet,
  use <strong>Extract Spec</strong>:
</p>
<ol>
  <li>Open a <code>.robot</code> file in the Explorer.</li>
  <li>Click <strong>Extract Spec</strong> in the toolbar.</li>
  <li>The LLM reverse-engineers a <code>.roboscope</code> YAML specification.</li>
  <li>Review and accept the result.</li>
</ol>
<p>
  This is useful for bringing existing test suites under specification-driven
  management, or for generating documentation from code.
</p>`
      }
    ]
  },

  // ─── 11. Advanced ─────────────────────────────────────────────────
  {
    id: 'advanced',
    title: 'Advanced',
    icon: '💡',
    subsections: [
      {
        id: 'websocket-updates',
        title: 'WebSocket Live Updates',
        content: `
<p>
  RoboScope uses <strong>WebSocket</strong> connections to deliver real-time updates
  without page refreshes. The frontend establishes a WebSocket connection upon login
  via the <code>useWebSocket</code> composable.
</p>
<h4>What Gets Updated Live</h4>
<ul>
  <li><strong>Run status changes</strong> &mdash; When a run transitions between states
      (pending &rarr; running &rarr; passed/failed), the status badge updates instantly
      on the Execution page, Dashboard, and any open Run Detail view.</li>
  <li><strong>Output streaming</strong> &mdash; Standard output and error from running tests
      are streamed to the Run Detail view in near real-time.</li>
  <li><strong>Sync progress</strong> &mdash; Repository sync operations update their status
      via WebSocket when completed.</li>
</ul>
<p>
  If the WebSocket connection is lost (e.g., due to a network interruption), the client
  automatically attempts to reconnect. A brief notification appears in the header
  area when the connection is disrupted.
</p>`,
        tip: 'If live updates seem stuck, check the browser console for WebSocket errors. A page refresh re-establishes the connection.'
      },
      {
        id: 'keyboard-shortcuts',
        title: 'Keyboard Shortcuts',
        content: `
<p>
  RoboScope supports several keyboard shortcuts for faster navigation and editing:
</p>
<table>
  <thead>
    <tr><th>Shortcut</th><th>Action</th><th>Context</th></tr>
  </thead>
  <tbody>
    <tr><td><code>Ctrl+S</code> / <code>Cmd+S</code></td><td>Save file</td><td>Explorer editor</td></tr>
    <tr><td><code>Ctrl+F</code> / <code>Cmd+F</code></td><td>Find in file</td><td>Explorer editor</td></tr>
    <tr><td><code>Ctrl+H</code> / <code>Cmd+H</code></td><td>Find and replace</td><td>Explorer editor</td></tr>
    <tr><td><code>Ctrl+G</code> / <code>Cmd+G</code></td><td>Go to line</td><td>Explorer editor</td></tr>
    <tr><td><code>Ctrl+Z</code> / <code>Cmd+Z</code></td><td>Undo</td><td>Explorer editor</td></tr>
    <tr><td><code>Ctrl+Shift+Z</code> / <code>Cmd+Shift+Z</code></td><td>Redo</td><td>Explorer editor</td></tr>
    <tr><td><code>Escape</code></td><td>Close modal/dialog</td><td>Global</td></tr>
  </tbody>
</table>
<p>
  All keyboard shortcuts follow platform conventions: <code>Ctrl</code> on Windows/Linux,
  <code>Cmd</code> on macOS.
</p>`
      },
      {
        id: 'workflow-tips',
        title: 'Tips for Efficient Workflows',
        content: `
<p>
  Make the most of RoboScope with these practical tips:
</p>
<h4>Organize Repositories Thoughtfully</h4>
<ul>
  <li>Use one repository per project or test domain (e.g., <code>web-tests</code>, <code>api-tests</code>).</li>
  <li>Enable auto-sync on Git repositories used in CI/CD workflows.</li>
  <li>Use descriptive repository names so team members can quickly identify the right one.</li>
</ul>
<h4>Leverage Environments</h4>
<ul>
  <li>Create separate environments for different testing contexts (e.g., Selenium vs. Browser Library).</li>
  <li>Clone environments when you only need to change one or two packages.</li>
  <li>Use environment variables to externalize configuration like URLs and credentials.</li>
</ul>
<h4>Monitor Quality Trends</h4>
<ul>
  <li>Check the Statistics page weekly to spot success rate regressions early.</li>
  <li>Address flaky tests promptly &mdash; they undermine trust in the test suite.</li>
  <li>Use the repository filter to isolate problems to specific test suites.</li>
</ul>
<h4>Team Collaboration</h4>
<ul>
  <li>Assign appropriate roles to team members following the principle of least privilege.</li>
  <li>Use the Dashboard as a shared team status board for testing progress.</li>
  <li>Download reports as ZIP archives when you need to share results outside of RoboScope.</li>
</ul>`
      },
      {
        id: 'troubleshooting',
        title: 'Troubleshooting Common Issues',
        content: `
<p>
  If you encounter problems, consult the following common issues and solutions:
</p>
<h4>Run Stays in "Pending" Status</h4>
<p>
  The task executor processes one run at a time. If another run is currently executing,
  your run will wait in the queue. Check the Execution page for any long-running or
  stuck runs and cancel them if necessary.
</p>
<h4>Git Clone or Sync Fails</h4>
<ul>
  <li>Verify the repository URL is correct and accessible from the server.</li>
  <li>For private repositories, ensure credentials or SSH keys are configured.</li>
  <li>Check if the specified branch exists on the remote.</li>
  <li>Review the server logs for detailed error messages.</li>
</ul>
<h4>Run Fails with "Error" Status</h4>
<p>
  An <code>error</code> status (different from <code>failed</code>) means the run could
  not be started or crashed unexpectedly. Common causes:
</p>
<ul>
  <li>Robot Framework is not installed in the selected environment.</li>
  <li>Required Python libraries are missing.</li>
  <li>The target path does not exist in the repository.</li>
  <li>Permission issues on the workspace or reports directory.</li>
</ul>
<h4>WebSocket Connection Issues</h4>
<p>
  If live updates are not working:
</p>
<ul>
  <li>Ensure your browser supports WebSockets (all modern browsers do).</li>
  <li>Check if a reverse proxy or firewall is blocking WebSocket connections.</li>
  <li>Look for connection errors in the browser&rsquo;s developer console (<code>F12</code>).</li>
  <li>Refresh the page to re-establish the connection.</li>
</ul>
<h4>Reports Not Generated</h4>
<p>
  If a run completes but no report appears:
</p>
<ul>
  <li>The run may have failed before Robot Framework produced <code>output.xml</code>.</li>
  <li>Check the run&rsquo;s stderr output for Python or Robot Framework errors.</li>
  <li>Verify that the <code>REPORTS_DIR</code> directory is writable by the application.</li>
</ul>`,
        tip: 'For persistent issues, check the backend logs with "make docker-logs" or review the uvicorn console output in development mode.'
      },
      {
        id: 'i18n',
        title: 'Language Support',
        content: `
<p>
  RoboScope supports multiple interface languages:
</p>
<table>
  <thead>
    <tr><th>Code</th><th>Language</th></tr>
  </thead>
  <tbody>
    <tr><td><code>en</code></td><td>English</td></tr>
    <tr><td><code>de</code></td><td>Deutsch (German)</td></tr>
    <tr><td><code>fr</code></td><td>Fran&ccedil;ais (French)</td></tr>
    <tr><td><code>es</code></td><td>Espa&ntilde;ol (Spanish)</td></tr>
  </tbody>
</table>
<p>
  To switch languages, use the <strong>language selector</strong> in the application header.
  The selected language is saved to your browser&rsquo;s local storage and persists
  across sessions. All UI labels, buttons, messages, and this documentation adapt
  to the selected language.
</p>`
      }
    ]
  },

  // ─── 12. Legal & About ──────────────────────────────────────────
  {
    id: 'legal',
    title: 'Legal & About',
    icon: 'info',
    subsections: [
      {
        id: 'footer',
        title: 'Footer',
        content: `
<p>
  A footer is displayed at the bottom of every page, containing:
</p>
<ul>
  <li>The <strong>copyright notice</strong> for viadee Unternehmensberatung AG.</li>
  <li>A link to the <strong>viadee.de</strong> website.</li>
  <li>A link to the <strong>Imprint</strong> (legal notice) page.</li>
</ul>`
      },
      {
        id: 'imprint',
        title: 'Imprint',
        content: `
<p>
  The <strong>Imprint</strong> page provides the legal notice required by German law
  (Impressum). It contains the company details of <em>viadee Unternehmensberatung AG</em>,
  including address, contact information, board of directors, commercial register entry,
  and VAT identification number.
</p>
<p>
  Access the Imprint page via the footer link or by navigating to <code>/imprint</code>.
</p>`
      }
    ]
  }
]

export default en
