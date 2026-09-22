import { api } from './client'
import type { ConnectorMeta, ObjectSchema, ColumnSchema } from '@/types'

export interface ConnectorHealthEntry {
  connector_id: string
  status: 'available' | 'unavailable' | 'error'
  message?: string
}

export interface ConnectorHealthReport {
  total: number
  available: number
  connectors: ConnectorHealthEntry[]
  checked_at: string
}

export const connectorsApi = {
  list: () => api.get<ConnectorMeta[]>('/connectors/'),
  get: (id: string) => api.get<ConnectorMeta>(`/connectors/${id}`),
  test: (id: string, config: Record<string, unknown>) =>
    api.post<{ success: boolean; error?: string }>(`/connectors/${id}/test`, { config }),
  health: () => api.get<ConnectorHealthReport>('/connectors/health'),
  objects: (id: string, config: Record<string, unknown>) =>
    api.post<ObjectSchema[]>(`/connectors/${id}/objects`, { config }),
  columns: (id: string, config: Record<string, unknown>, objectName: string) =>
    api.post<ColumnSchema[]>(`/connectors/${id}/columns`, { config, object_name: objectName }),
}
