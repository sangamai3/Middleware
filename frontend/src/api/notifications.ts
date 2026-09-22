import { api } from './client'

export type AlertTrigger =
  | 'flow_failed'
  | 'flow_slow'
  | 'error_rate_high'
  | 'run_started'
  | 'run_completed'

export interface AlertChannel {
  channel_type: 'slack' | 'webhook'
  webhook_url?: string
  url?: string
  secret?: string
  username?: string
  icon_emoji?: string
}

export interface AlertRule {
  rule_id: string
  name: string
  trigger: AlertTrigger
  flow_ids: string[] | null
  conditions: Record<string, unknown>
  channels: AlertChannel[]
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateAlertRule {
  name: string
  trigger: AlertTrigger
  flow_ids?: string[] | null
  conditions?: Record<string, unknown>
  channels: AlertChannel[]
  is_active?: boolean
}

export const notificationsApi = {
  listRules: () => api.get<AlertRule[]>('/notifications/rules'),
  createRule: (body: CreateAlertRule) => api.post<AlertRule>('/notifications/rules', body),
  getRule: (id: string) => api.get<AlertRule>(`/notifications/rules/${id}`),
  updateRule: (id: string, body: Partial<CreateAlertRule>) =>
    api.put<AlertRule>(`/notifications/rules/${id}`, body),
  deleteRule: (id: string) => api.delete<void>(`/notifications/rules/${id}`),
  testRule: (id: string) =>
    api.post<{ fired: boolean; rule_id: string; channels_attempted: number }>(
      `/notifications/rules/${id}/test`
    ),
}
