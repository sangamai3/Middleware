import { api } from './client'

export interface AiGenerateFlowResponse {
  flow_yaml: string
  flow_definition: Record<string, unknown>
  provider: string
  model: string
}

export interface AiMappingSuggestion {
  source_field: string
  target_field: string
  confidence: number
  transform: string | null
  reason: string
}

export const aiApi = {
  generateFlow: (body: {
    description: string
    available_connectors?: string[]
    available_connections?: { connection_id: string; connector_id: string; name: string }[]
    provider?: 'anthropic' | 'openai'
  }) => api.post<AiGenerateFlowResponse>('/ai/generate-flow', body),

  suggestMapping: (body: {
    source_schema: { name: string; data_type?: string }[]
    target_schema: { name: string; data_type?: string }[]
    provider?: 'anthropic' | 'openai'
  }) =>
    api.post<{ suggestions: AiMappingSuggestion[]; count: number }>(
      '/ai/suggest-mapping',
      body,
    ),
}
