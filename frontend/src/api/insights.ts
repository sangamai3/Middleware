import { api } from './client'

function qs(params?: Record<string, string | number | undefined>): string {
  if (!params) return ''
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

export interface InsightsOverview {
  total_flows: number
  runs_today: number
  errors_today: number
  error_rate: number
  avg_duration_ms: number
}

export interface FlowInsight {
  flow_id: string
  flow_name: string
  run_count: number
  error_count: number
  error_rate: number
  avg_duration_ms: number
  last_run_at: string | null
  last_status: string
}

export interface RunHistoryItem {
  run_id: string
  flow_id: string
  flow_name: string
  status: string
  trigger_type: string
  triggered_by: string
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
  rows_processed: number
  rows_failed: number
  correlation_id: string | null
  error_message: string | null
}

export interface RunHistory {
  total: number
  runs: RunHistoryItem[]
}

export interface MetricsBucket {
  ts: string
  run_count: number
  error_count: number
  total_rows: number
  total_duration_ms: number
  p50_ms: number | null
  p95_ms: number | null
  p99_ms: number | null
}

export interface LogEntry {
  id: number
  run_id: string
  flow_id: string
  step_id: string | null
  correlation_id: string | null
  level: string
  message: string
  payload_preview: string | null
  timestamp: string | null
}

export interface LogSearchResult {
  total: number
  logs: LogEntry[]
}

export interface BusinessEvent {
  id: number
  flow_id: string
  run_id: string
  step_id: string | null
  correlation_id: string | null
  event_name: string
  payload: Record<string, unknown>
  occurred_at: string | null
}

export interface BusinessEventResult {
  total: number
  events: BusinessEvent[]
}

export interface StepDetail {
  step_id: string
  step_type: string
  step_label?: string
  connector_id?: string | null
  status: string
  duration_ms: number | null
  rows_in: number
  rows_out: number
  error_type: string | null
  error_message: string | null
  retry_count: number
  started_at: string | null
}

export interface RunLogLine {
  level: string
  message: string
  step_id: string | null
  timestamp: string | null
}

export interface RunDetail {
  run_id: string
  flow_id: string
  flow_name: string
  correlation_id: string | null
  status: string
  trigger_type: string
  triggered_by: string
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
  rows_processed: number
  rows_failed: number
  error_message: string | null
  steps: StepDetail[]
  logs: RunLogLine[]
  business_events: Array<{
    event_name: string
    payload: Record<string, unknown>
    step_id: string | null
    occurred_at: string | null
  }>
}

export const insightsApi = {
  overview: () => api.get<InsightsOverview>('/insights/overview'),

  flows: (params?: { from_dt?: string; to_dt?: string }) =>
    api.get<FlowInsight[]>(`/insights/flows${qs(params)}`),

  flowRuns: (
    flowId: string,
    params?: {
      status?: string
      from_dt?: string
      to_dt?: string
      triggered_by?: string
      limit?: number
      offset?: number
    },
  ) => api.get<RunHistory>(`/insights/flows/${flowId}/runs${qs(params)}`),

  flowMetrics: (
    flowId: string,
    params?: { from_dt?: string; to_dt?: string; granularity?: string },
  ) => api.get<MetricsBucket[]>(`/insights/flows/${flowId}/metrics${qs(params)}`),

  searchLogs: (params?: {
    q?: string
    flow_id?: string
    run_id?: string
    level?: string
    from_dt?: string
    to_dt?: string
    limit?: number
    offset?: number
  }) => api.get<LogSearchResult>(`/insights/logs${qs(params)}`),

  runLogs: (runId: string) =>
    api.get<RunLogLine[]>(`/insights/logs/${runId}`),

  businessEvents: (params?: {
    flow_id?: string
    event_name?: string
    correlation_id?: string
    from_dt?: string
    to_dt?: string
    limit?: number
    offset?: number
  }) => api.get<BusinessEventResult>(`/insights/events${qs(params)}`),

  runDetail: (runId: string) =>
    api.get<RunDetail>(`/insights/runs/${runId}`),
}
