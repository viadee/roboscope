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
  default_runner_type?: string
  max_docker_containers?: number
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

// --- AI Generation request types ---

export interface AiProviderCreateRequest {
  name: string
  provider_type: 'openai' | 'anthropic' | 'openrouter' | 'ollama'
  api_base_url?: string | null
  api_key?: string | null
  model_name: string
  temperature?: number
  max_tokens?: number
  is_default?: boolean
}

export interface AiProviderUpdateRequest {
  name?: string
  provider_type?: string
  api_base_url?: string | null
  api_key?: string | null
  model_name?: string
  temperature?: number
  max_tokens?: number
  is_default?: boolean
}

export interface AiGenerateRequest {
  repository_id: number
  spec_path: string
  provider_id?: number | null
  force?: boolean
}

export interface AiReverseRequest {
  repository_id: number
  robot_path: string
  provider_id?: number | null
  output_path?: string | null
}

export interface AiValidateSpecRequest {
  content: string
}
