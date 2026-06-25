/** API request types */

export interface LoginRequest {
  email: string
  password: string
}

export interface RepoCreateRequest {
  // Optional for git repos — backend derives the name from the git
  // URL basename when omitted. Required for local repos.
  name?: string
  repo_type?: 'git' | 'local'
  git_url?: string
  local_path?: string
  default_branch?: string
  auto_sync?: boolean
  sync_interval_minutes?: number
  pre_run_sync?: boolean
  environment_id?: number | null
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
  index_url?: string | null
  extra_index_url?: string | null
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
  provider_type: 'openai' | 'anthropic' | 'openrouter' | 'ollama' | 'litellm'
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

export interface AiAnalyzeRequest {
  report_id: number
  provider_id?: number | null
  /** Frontend i18n locale (de/en/fr/es/zh) so the analysis prose comes back
   *  in the user's current UI language. */
  language?: string | null
  /** Analysis length: concise | standard | detailed. */
  verbosity?: string | null
}

export interface AiValidateSpecRequest {
  content: string
}

export interface RecordingCreateRequest {
  repository_id: number
  environment_id?: number | null
  source?: 'playwright' | 'extension'
  target_url?: string | null
  target_file_path?: string | null
  target_library?: 'Browser' | 'SeleniumLibrary'
}
