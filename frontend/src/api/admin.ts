import { api } from './client'

export interface AdminUser {
  user_id: string
  email: string
  role: string
  is_active: boolean
  created_at: string
}

export interface AuditEntry {
  id: number
  actor_id: string
  actor_email: string
  action: string
  resource_type: string
  resource_id: string
  entry_hash: string
  created_at: string
}

export interface SystemStats {
  connector_count: number
  flow_count: number
  user_count: number
  run_count_24h: number
  error_rate_24h: number
}

export const adminApi = {
  listUsers: () => api.get<AdminUser[]>('/users'),
  updateUserRole: (userId: string, role: string) =>
    api.put<AdminUser>(`/users/${userId}`, { role }),
  deactivateUser: (userId: string) =>
    api.put<AdminUser>(`/users/${userId}`, { is_active: false }),

  listAuditLog: (limit = 100) =>
    api.get<AuditEntry[]>(`/audit?limit=${limit}`),
  verifyAuditChain: () =>
    api.get<{ valid: boolean; broken_at?: number }>('/audit/verify'),

  systemStats: () => api.get<SystemStats>('/health/deps'),
}
