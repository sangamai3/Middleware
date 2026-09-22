import { api } from './client'
import type { FlowDefinition, ExecutionRun } from '@/types'

export const flowsApi = {
  list: () => api.get<{ flow_id: string; name: string; status: string }[]>('/flows/'),
  get: (id: string) => api.get<FlowDefinition>(`/flows/${id}`),
  create: (definition: Partial<FlowDefinition>) =>
    api.post<{ flow_id: string; status: string }>('/flows/', { definition }),
  update: (id: string, definition: Partial<FlowDefinition>) =>
    api.put<{ flow_id: string; status: string }>(`/flows/${id}`, { definition }),
  delete: (id: string) => api.delete<{ deleted: string }>(`/flows/${id}`),
  validate: (id: string) =>
    api.post<{ valid: boolean; warnings?: string[]; error?: string }>(`/flows/${id}/validate`),
  deploy: (id: string) =>
    api.post<{ flow_id: string; status: string }>(`/flows/${id}/deploy`),
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
