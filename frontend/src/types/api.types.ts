/** API request types */

export interface LoginRequest {
  email: string
  password: string
}

export interface RepoCreateRequest {
  name: string
  repo_type?: 'git' | 'local'
  git_url?: string
  local_path?: string
  default_branch?: string
  auto_sync?: boolean
  sync_interval_minutes?: number
}

export interface RunCreateRequest {
  repository_id: number
  environment_id?: number | null
  run_type?: string
  runner_type?: string
  target_path: string
  branch?: string
  tags_include?: string | null
  tags_exclude?: string | null
  variables?: Record<string, string> | null
  parallel?: boolean
  max_retries?: number
  timeout_seconds?: number
}

export interface ScheduleCreateRequest {
  name: string
  cron_expression: string
  repository_id: number
  environment_id?: number | null
  target_path: string
  branch?: string
  runner_type?: string
  tags_include?: string | null
  tags_exclude?: string | null
}

export interface EnvCreateRequest {
  name: string
  python_version?: string
  docker_image?: string | null
  is_default?: boolean
  description?: string | null
}

export interface PackageCreateRequest {
  package_name: string
  version?: string | null
}

export interface SettingUpdateRequest {
  key: string
  value: string
}
