import { api } from './client'

export interface ScheduledJob {
  flow_id: string
  flow_name: string
  cron_expr: string | null
  interval_seconds: number | null
  timezone: string
  is_active: boolean
  last_run_at: string | null
  next_run_at: string | null
  trigger_type: 'cron' | 'interval'
  trigger_label: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateJob {
  flow_id: string
  flow_name?: string
  cron_expr?: string | null
  interval_seconds?: number | null
  timezone?: string
  is_active?: boolean
}

export const schedulerApi = {
  listJobs: () => api.get<ScheduledJob[]>('/scheduler/jobs'),
  createJob: (body: CreateJob) => api.post<ScheduledJob>('/scheduler/jobs', body),
  getJob: (flowId: string) => api.get<ScheduledJob>(`/scheduler/jobs/${flowId}`),
  updateJob: (flowId: string, body: Partial<CreateJob>) =>
    api.patch<ScheduledJob>(`/scheduler/jobs/${flowId}`, body),
  deleteJob: (flowId: string) => api.delete<void>(`/scheduler/jobs/${flowId}`),
  triggerJob: (flowId: string) =>
    api.post<{ flow_id: string; triggered_at: string; status: string }>(
      `/scheduler/jobs/${flowId}/trigger`
    ),
}
