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
        title: 'What is mateoX?',
        content: `
<p>
  <strong>mateoX</strong> is a web-based test management tool designed specifically for
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
        tip: 'mateoX works best with Chromium-based browsers (Chrome, Edge) or Firefox for the full CodeMirror editing experience.'
      },
      {
        id: 'login',
        title: 'Logging In',
        content: `
<p>
  When you first open mateoX, you will be presented with the <strong>Login</strong> screen.
  Enter your email address and password to authenticate.
</p>
<h4>Default Administrator Account</h4>
<table>
  <thead>
    <tr><th>Field</th><th>Value</th></tr>
  </thead>
  <tbody>
    <tr><td>Email</td><td><code>admin@mateox.local</code></td></tr>
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
  mateoX uses JWT-based authentication. Your session token is automatically refreshed
  as long as the application is open. If the token expires (e.g., after a long
  inactivity period), you will be redirected to the login page.
</p>`,
        tip: 'If you forget your password, an admin user can reset it from the Settings page.'
      },
      {
        id: 'ui-layout',
        title: 'UI Layout',
        content: `
<p>The mateoX interface consists of three main areas:</p>
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
    mateoX design system.
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
  mateoX implements a hierarchical role-based access control (RBAC) system.
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
  The <strong>Dashboard</strong> is the default landing page after login. It provides
  a high-level overview of your testing activity and repository health, helping you
  quickly assess the current state of your project.
</p>
<p>
  The Dashboard is divided into three sections: <strong>KPI Cards</strong> at the top,
  a <strong>Recent Runs</strong> table in the middle, and a <strong>Repository Summary</strong>
  at the bottom.
</p>`
      },
      {
        id: 'kpi-cards',
        title: 'KPI Cards',
        content: `
<p>
  Four key performance indicator cards are displayed at the top of the Dashboard:
</p>
<table>
  <thead>
    <tr><th>Card</th><th>Description</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Runs (30d)</strong></td>
      <td>Total number of test runs executed in the last 30 days.</td>
    </tr>
    <tr>
      <td><strong>Success Rate</strong></td>
      <td>Percentage of runs that completed with all tests passing (last 30 days).</td>
    </tr>
    <tr>
      <td><strong>Avg Duration</strong></td>
      <td>Average wall-clock time of completed test runs over the last 30 days.</td>
    </tr>
    <tr>
      <td><strong>Active Repos</strong></td>
      <td>Number of repositories that have had at least one run in the last 30 days.</td>
    </tr>
  </tbody>
</table>
<p>
  Each card uses the mateoX design system: white background, teal accent for positive
  trends, and gold for warnings. The values update automatically when navigating to
  the Dashboard.
</p>`,
        tip: 'KPI cards reflect the last 30 days of activity. For longer time ranges, use the Statistics page.'
      },
      {
        id: 'recent-runs',
        title: 'Recent Runs Table',
        content: `
<p>
  Below the KPI cards, a table lists the most recent test runs across all repositories.
  Each row shows:
</p>
<ul>
  <li><strong>Run ID</strong> &mdash; A unique identifier for the run.</li>
  <li><strong>Repository</strong> &mdash; The repository name the run was triggered against.</li>
  <li><strong>Status</strong> &mdash; A colored badge indicating the run state: <code>passed</code>, <code>failed</code>, <code>running</code>, <code>pending</code>, <code>error</code>, <code>cancelled</code>, or <code>timeout</code>.</li>
  <li><strong>Duration</strong> &mdash; How long the run took (or how long it has been running).</li>
  <li><strong>Triggered by</strong> &mdash; The user who started the run.</li>
  <li><strong>Date</strong> &mdash; Timestamp of when the run was initiated.</li>
</ul>
<p>
  Clicking a row navigates to the detailed <strong>Run Details</strong> page where you
  can inspect output logs, retry, or cancel the run.
</p>`
      },
      {
        id: 'repo-summary',
        title: 'Repository Overview',
        content: `
<p>
  The bottom section of the Dashboard shows a summary of all registered repositories.
  For each repository, you can see:
</p>
<ul>
  <li>Repository name and type (Git or Local).</li>
  <li>Number of test files detected.</li>
  <li>Last sync timestamp.</li>
  <li>Latest run status badge.</li>
</ul>
<p>
  This provides a quick glance at which repositories are healthy and which may need
  attention. Clicking a repository name takes you to the <strong>Explorer</strong> view
  for that repository.
</p>`,
        tip: 'If a repository shows a stale sync timestamp, navigate to Repositories and trigger a manual sync.'
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
  test repositories. mateoX supports two types of repositories:
</p>
<ul>
  <li><strong>Git Repositories</strong> &mdash; Cloned from a remote URL, with branch selection and sync capabilities.</li>
  <li><strong>Local Folders</strong> &mdash; Pointing to a directory on the server&rsquo;s filesystem.</li>
</ul>
<p>
  All repository data is stored under the <code>WORKSPACE_DIR</code> directory
  (default: <code>~/.mateox/workspace</code>). Only users with the <strong>Editor</strong>
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
  mateoX uses <em>GitPython</em> to clone the repository into the workspace directory.
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
        title: 'Sync & Auto-Sync',
        content: `
<p>
  Git repositories can be synchronized to pull the latest changes from the remote:
</p>
<ul>
  <li><strong>Manual Sync</strong> &mdash; Click the <strong>Sync</strong> button on a repository row. This performs a <code>git pull</code> on the configured branch.</li>
  <li><strong>Auto-Sync</strong> &mdash; Enable the auto-sync toggle for a repository. When enabled, mateoX will automatically pull changes at a configurable interval before each test run.</li>
</ul>
<p>
  The sync status is indicated by a timestamp showing the last successful sync. If a
  sync fails (e.g., merge conflicts), an error badge appears next to the repository name.
</p>`,
        tip: 'Auto-sync ensures you always test against the latest code. Enable it for CI/CD-like workflows.'
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
  <strong>Warning:</strong> Deleting a repository removes it from mateoX and deletes
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
</ul>
<p>
  A <strong>repository selector</strong> dropdown at the top lets you switch between
  registered repositories without leaving the Explorer.
</p>`
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

  // ─── 5. Execution ─────────────────────────────────────────────────
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
  Since mateoX uses a single-worker executor, runs are processed one at a time in
  FIFO (first-in, first-out) order.
</p>`,
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
  to terminate it. The underlying process is sent a termination signal and the run status
  changes to <code>cancelled</code>. Requires <strong>Runner</strong> role or above.
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
  completed run, Robot Framework produces an <code>output.xml</code> file that mateoX
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
  Displays a structured overview of the test execution: total tests, passed, failed,
  skipped, critical tests, and execution timestamps. Results are broken down by suite,
  showing individual test case outcomes in an expandable tree.
</p>
<h4>HTML Report Tab</h4>
<p>
  Embeds the original Robot Framework HTML report (<code>report.html</code>) in an iframe.
  This is the same report you would get from running <code>robot</code> on the command line,
  complete with interactive charts, keyword details, and log links.
</p>
<h4>XML View Tab</h4>
<p>
  Renders the raw <code>output.xml</code> content with syntax highlighting. This is useful
  for advanced users who need to inspect the machine-readable output, debug custom
  listeners, or verify specific XML elements.
</p>`,
        tip: 'The HTML Report tab provides the richest view. Use it for investigating individual test case failures and keyword-level logs.'
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
  any code changes. mateoX detects flaky tests by analyzing the pass/fail history of
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
  <li><strong>Deep Analysis</strong> &mdash; On-demand analysis of keyword analytics, test quality metrics, and maintenance indicators. Select specific KPIs and start an analysis to explore deeper insights.</li>
</ul>`,
        tip: 'Use the Deep Analysis tab to investigate keyword durations, assertion density, and error patterns across your test suites.'
      }
    ]
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
  (default: <code>~/.mateox/venvs</code>). Managing environments requires the
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
  mateoX creates a Python <code>venv</code> in the background using the system Python.
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
  <li><code>robotframework-browser</code> &mdash; Playwright-based browser testing.</li>
  <li><code>robotframework-requests</code> &mdash; HTTP API testing.</li>
  <li><code>robotframework-databaselibrary</code> &mdash; Database testing.</li>
  <li><code>robotframework-sshlibrary</code> &mdash; SSH connections.</li>
  <li><code>robotframework-excellibrary</code> &mdash; Excel file handling.</li>
</ul>
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
        tip: 'Always install robotframework first before adding library packages to avoid dependency issues.'
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
      }
    ]
  },

  // ─── 10. Advanced ─────────────────────────────────────────────────
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
  mateoX uses <strong>WebSocket</strong> connections to deliver real-time updates
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
  mateoX supports several keyboard shortcuts for faster navigation and editing:
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
  Make the most of mateoX with these practical tips:
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
  <li>Download reports as ZIP archives when you need to share results outside of mateoX.</li>
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
  mateoX supports multiple interface languages:
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

  // ─── 11. Legal & About ──────────────────────────────────────────
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
  <li>A link to the <strong>mateo-automation.com</strong> website.</li>
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
