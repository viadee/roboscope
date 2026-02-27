/** Domain types matching backend schemas */

export type Role = 'viewer' | 'runner' | 'editor' | 'admin'
export type RunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error' | 'cancelled' | 'timeout'
export type RunType = 'single' | 'folder' | 'batch' | 'scheduled'
export type RunnerType = 'subprocess' | 'docker'

export interface User {
  id: number
  email: string
  username: string
  role: Role
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface Repository {
  id: number
  name: string
  repo_type: 'git' | 'local'
  git_url: string | null
  default_branch: string
  local_path: string
  last_synced_at: string | null
  auto_sync: boolean
  sync_interval_minutes: number
  sync_status: string | null
  sync_error: string | null
  created_by: number
  environment_id: number | null
  created_at: string
  updated_at: string
}

export interface Branch {
  name: string
  is_active: boolean
}

export interface ProjectMember {
  id: number
  user_id: number
  repository_id: number
  role: 'viewer' | 'runner' | 'editor'
  username: string
  email: string
  created_at: string
}

export interface TreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  extension: string | null
  children: TreeNode[] | null
  test_count: number
}

export interface FileContent {
  path: string
  name: string
  content: string
  extension: string | null
  line_count: number
  is_binary?: boolean
}

export interface TestCaseInfo {
  name: string
  file_path: string
  suite_name: string
  tags: string[]
  documentation: string
  line_number: number
}

export interface SearchResult {
  type: 'testcase' | 'keyword' | 'file'
  name: string
  file_path: string
  line_number: number
  context: string
}

export interface ExecutionRun {
  id: number
  repository_id: number
  environment_id: number | null
  run_type: RunType
  runner_type: RunnerType
  status: RunStatus
  target_path: string
  branch: string
  tags_include: string | null
  tags_exclude: string | null
  parallel: boolean
  retry_count: number
  max_retries: number
  timeout_seconds: number
  task_id: string | null
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  triggered_by: number
  error_message: string | null
  created_at: string
}

export interface RunListResponse {
  items: ExecutionRun[]
  total: number
  page: number
  page_size: number
}

export interface Schedule {
  id: number
  name: string
  cron_expression: string
  repository_id: number
  environment_id: number | null
  target_path: string
  branch: string
  runner_type: RunnerType
  tags_include: string | null
  tags_exclude: string | null
  is_active: boolean
  last_run_at: string | null
  next_run_at: string | null
  created_by: number
  created_at: string
}

export interface Environment {
  id: number
  name: string
  python_version: string
  venv_path: string | null
  docker_image: string | null
  default_runner_type: string
  max_docker_containers: number
  is_default: boolean
  description: string | null
  created_by: number
  created_at: string
  updated_at: string
}

export interface EnvironmentPackage {
  id: number
  environment_id: number
  package_name: string
  version: string | null
  installed_version: string | null
  install_status: 'pending' | 'installing' | 'installed' | 'failed'
  install_error: string | null
}

export interface EnvironmentVariable {
  id: number
  environment_id: number
  key: string
  value: string
  is_secret: boolean
}

export interface Report {
  id: number
  execution_run_id: number | null
  archive_name: string | null
  total_tests: number
  passed_tests: number
  failed_tests: number
  skipped_tests: number
  total_duration_seconds: number
  created_at: string
}

export interface TestResult {
  id: number
  report_id: number
  suite_name: string
  test_name: string
  status: string
  duration_seconds: number
  error_message: string | null
  tags: string | null
  start_time: string | null
  end_time: string | null
}

export interface ReportDetail {
  report: Report
  test_results: TestResult[]
}

export interface TestHistoryPoint {
  report_id: number
  date: string
  status: string
  duration_seconds: number
  error_message: string | null
}

export interface TestHistory {
  test_name: string
  suite_name: string
  history: TestHistoryPoint[]
  total_runs: number
  pass_count: number
  fail_count: number
  pass_rate: number
}

export interface UniqueTest {
  test_name: string
  suite_name: string
  last_status: string
  run_count: number
}

export interface OverviewKpi {
  total_runs: number
  passed_runs: number
  failed_runs: number
  success_rate: number
  avg_duration_seconds: number
  total_tests: number
  flaky_tests: number
  active_repos: number
}

export interface SuccessRatePoint {
  date: string
  success_rate: number
  total_runs: number
}

export interface TrendPoint {
  date: string
  passed: number
  failed: number
  error: number
  total: number
  avg_duration: number
}

export interface FlakyTest {
  test_name: string
  suite_name: string
  total_runs: number
  pass_count: number
  fail_count: number
  flaky_rate: number
  last_status: string
}

export interface AppSetting {
  id: number
  key: string
  value: string
  value_type: string
  category: string
  description: string | null
}

// --- Docker status types ---

export interface DockerImage {
  repository: string
  tag: string
  size: number
  created: string
}

export interface DockerStatus {
  connected: boolean
  version?: string
  api_version?: string
  os?: string
  arch?: string
  default_image: string
  running_containers?: number
  images?: DockerImage[]
  error?: string
}

// --- Analysis types ---

export interface AnalysisReport {
  id: number
  repository_id: number | null
  status: 'pending' | 'running' | 'completed' | 'error'
  selected_kpis: string[]
  date_from: string | null
  date_to: string | null
  results: Record<string, any> | null
  error_message: string | null
  progress: number
  reports_analyzed: number
  triggered_by: number
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface KpiMeta {
  id: string
  name: string
  category: string
  description: string
}

// --- Deep XML data types ---

export interface XmlMessage {
  timestamp: string
  level: string
  text: string
}

export interface XmlKeyword {
  name: string
  type: string
  library: string
  status: string
  start_time: string
  end_time: string
  duration: number
  doc: string
  arguments: string[]
  messages: XmlMessage[]
  keywords: XmlKeyword[]
}

export interface XmlTest {
  name: string
  status: string
  start_time: string
  end_time: string
  duration: number
  doc: string
  tags: string[]
  error_message: string
  keywords: XmlKeyword[]
}

export interface XmlSuite {
  name: string
  source: string
  status: string
  start_time: string
  end_time: string
  duration: number
  doc: string
  suites: XmlSuite[]
  tests: XmlTest[]
}

export interface XmlReportData {
  suites: XmlSuite[]
  statistics: Record<string, unknown>
  generated: string
}

// --- Library Check types ---

export interface LibraryCheckItem {
  library_name: string
  pypi_package: string | null
  status: 'installed' | 'missing' | 'builtin'
  installed_version: string | null
  files: string[]
  docker_status: 'installed' | 'missing' | null
  docker_installed_version: string | null
}

export interface LibraryCheckResponse {
  repo_id: number
  environment_id: number
  environment_name: string
  total_libraries: number
  missing_count: number
  installed_count: number
  builtin_count: number
  libraries: LibraryCheckItem[]
  docker_image: string | null
  docker_missing_count: number
}

// --- AI Generation types ---

export type AiProviderType = 'openai' | 'anthropic' | 'openrouter' | 'ollama'
export type AiJobStatus = 'pending' | 'running' | 'completed' | 'failed'
export type AiJobType = 'generate' | 'reverse' | 'analyze'

export interface AiProvider {
  id: number
  name: string
  provider_type: AiProviderType
  api_base_url: string | null
  has_api_key: boolean
  model_name: string
  temperature: number
  max_tokens: number
  is_default: boolean
  created_by: number
  created_at: string
  updated_at: string
}

export interface AiJob {
  id: number
  job_type: AiJobType
  status: AiJobStatus
  repository_id: number
  provider_id: number
  report_id: number | null
  spec_path: string
  target_path: string | null
  result_preview: string | null
  error_message: string | null
  token_usage: number | null
  triggered_by: number
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface DriftResult {
  spec_file: string
  target_file: string
  status: 'in_sync' | 'drifted' | 'missing'
}

export interface DriftResponse {
  repository_id: number
  results: DriftResult[]
}

export interface ValidateSpecResponse {
  valid: boolean
  errors: string[]
  test_count: number
}
