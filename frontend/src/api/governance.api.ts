import apiClient from './client'

export interface FeaturesResponse {
  /** Effective on/off value per feature flag. */
  flags: Record<string, boolean>
  /** True when the flag was set via an ENV override (UI shows it non-editable). */
  locked: Record<string, boolean>
}

/** Fetch the resolved deployment feature flags. */
export async function getFeatures(): Promise<FeaturesResponse> {
  const response = await apiClient.get<FeaturesResponse>('/config/features')
  return response.data
}
