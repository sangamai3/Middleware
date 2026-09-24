import { api } from './client'
import type { FlowDefinition, ExecutionRun } from '@/types'

export interface FlowPreviewResult {
  step_id: string
  step_label?: string
  steps_executed?: string[]
  columns: { name: string; data_type: string }[]
  rows: Record<string, unknown>[]
  row_count: number
  preview_row_count: number
  truncated: boolean
  input_format?: string
  output_format?: string
  formatted_output?: {
    format: string
    content: string
    truncated: boolean
    row_count: number
    label: string
  }
  error?: string
}

export const flowsApi = {
  list: () =>
    api.get<{ flow_id: string; name: string; status: string; created_at?: string; updated_at?: string }[]>(
      '/flows/',
    ),
  get: (id: string) => api.get<FlowDefinition>(`/flows/${id}`),
  create: (definition: Partial<FlowDefinition>) =>
    api.post<{ flow_id: string; status: string }>('/flows/', { definition }),
  update: (id: string, definition: Partial<FlowDefinition>) =>
    api.put<{ flow_id: string; status: string }>(`/flows/${id}`, { definition }),
  delete: (id: string) => api.delete<{ deleted: string }>(`/flows/${id}`),
  validate: (id: string) =>
    api.post<{ valid: boolean; warnings?: string[]; error?: string }>(`/flows/${id}/validate`),
  preview: (definition: FlowDefinition, stepId: string, limit = 25) =>
    api.post<FlowPreviewResult>('/flows/preview', {
      definition,
      step_id: stepId,
      limit,
    }),
  deploy: (id: string) =>
    api.post<{ flow_id: string; status: string }>(`/flows/${id}/deploy`),
  dockerCompose: (
    id: string,
    body: {
      definition?: FlowDefinition
      memory_profile?: 'minimal' | 'standard' | 'large'
      image_tag?: string
      control_plane_url?: string
      host_data_root?: string | null
    },
  ) =>
    api.post<{
      manifest: {
        connector_ids: string[]
        pip_extras: string[]
        memory_profile: string
        service_name: string
      }
      compose_yaml: string
      env_example: string
    }>(`/flows/${id}/docker-compose`, body),
  execute: (id: string, variables: Record<string, unknown> = {}) =>
    api.post<{ run_id: string; status: string; rows_processed: number; error_message: string | null }>(
      `/flows/${id}/execute`,
      { variables },
    ),
}

export const runsApi = {
  list: () => api.get<{ run_id: string; flow_id: string; status: string; started_at: string }[]>('/runs/'),
  get: (id: string) => api.get<ExecutionRun>(`/runs/${id}`),
}
