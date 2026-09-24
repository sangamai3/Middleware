import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { schedulerApi, type ScheduledJob } from '@/api/scheduler'
import { flowsApi } from '@/api/flows'
import {
  CronScheduleBuilder,
  buildScheduleFromState,
  defaultCronScheduleState,
  parseScheduleToState,
} from '@/components/scheduler/CronScheduleBuilder'
import type { CronScheduleState } from '@/lib/cronSchedule'
import './SchedulerPage.css'

export function SchedulerPage() {
  const qc = useQueryClient()
  const [formMode, setFormMode] = useState<'create' | 'edit' | null>(null)
  const [editingJob, setEditingJob] = useState<ScheduledJob | null>(null)

  const closeForm = () => {
    setFormMode(null)
    setEditingJob(null)
  }

  const openCreate = () => {
    setEditingJob(null)
    setFormMode('create')
  }

  const openEdit = (job: ScheduledJob) => {
    setEditingJob(job)
    setFormMode('edit')
  }

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['scheduler-jobs'],
    queryFn: () => schedulerApi.listJobs(),
    retry: false,
  })

  const toggleMutation = useMutation({
    mutationFn: ({ flowId, active }: { flowId: string; active: boolean }) =>
      schedulerApi.updateJob(flowId, { is_active: active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler-jobs'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (flowId: string) => schedulerApi.deleteJob(flowId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler-jobs'] }),
  })

  const triggerMutation = useMutation({
    mutationFn: (flowId: string) => schedulerApi.triggerJob(flowId),
  })

  return (
    <div className="scheduler">
      <div className="scheduler__header">
        <div>
          <h1 className="scheduler__title">Flow Scheduler</h1>
          <p className="scheduler__sub">
            Schedule flows to run automatically. Click <strong>+ Schedule flow</strong> to use the visual builder (daily, weekly, every N minutes, and more).
          </p>
        </div>
        <button className="sched-btn sched-btn--primary" onClick={openCreate}>
          + Schedule flow
        </button>
      </div>

      {formMode && (
        <JobForm
          mode={formMode}
          job={editingJob}
          onClose={closeForm}
          onSaved={() => {
            closeForm()
            qc.invalidateQueries({ queryKey: ['scheduler-jobs'] })
          }}
        />
      )}

      {isLoading ? (
        <div className="sched-loading">Loading schedules…</div>
      ) : jobs.length === 0 && !formMode ? (
        <div className="sched-empty">
          <div className="sched-empty__icon">⏱</div>
          <div>No scheduled flows yet. Create a schedule to run flows automatically.</div>
        </div>
      ) : (
        <table className="sched-table">
          <thead>
            <tr>
              <th>Flow</th>
              <th>Schedule</th>
              <th>Next run</th>
              <th>Last run</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job: ScheduledJob) => (
              <tr key={job.flow_id} className={job.is_active ? '' : 'sched-table__row--inactive'}>
                <td>
                  <div className="sched-flow-name">{job.flow_name || job.flow_id}</div>
                  <div className="sched-flow-id">{job.flow_id}</div>
                </td>
                <td>
                  <div className="sched-trigger">
                    <span className="trigger-type-badge">{job.trigger_type}</span>
                    <span className="trigger-expr">
                      {job.cron_expr || (job.interval_seconds ? `${job.interval_seconds}s` : '—')}
                    </span>
                  </div>
                  <div className="sched-trigger-label">{job.trigger_label}</div>
                </td>
                <td className="sched-time">
                  {job.next_run_at ? new Date(job.next_run_at).toLocaleString() : '—'}
                </td>
                <td className="sched-time">
                  {job.last_run_at ? new Date(job.last_run_at).toLocaleString() : 'Never'}
                </td>
                <td>
                  <span className={`status-dot${job.is_active ? ' status-dot--active' : ''}`}>
                    {job.is_active ? 'active' : 'paused'}
                  </span>
                </td>
                <td>
                  <div className="sched-actions">
                    <button
                      className="sched-link-btn"
                      onClick={() => openEdit(job)}
                    >Edit</button>
                    <button
                      className="sched-link-btn"
                      onClick={() => triggerMutation.mutate(job.flow_id)}
                      title="Run now"
                    >▶ Run</button>
                    <button
                      className="sched-link-btn"
                      onClick={() => toggleMutation.mutate({ flowId: job.flow_id, active: !job.is_active })}
                    >{job.is_active ? 'Pause' : 'Resume'}</button>
                    <button
                      className="sched-link-btn sched-link-btn--danger"
                      onClick={() => deleteMutation.mutate(job.flow_id)}
                    >Delete</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

// ── Create / edit job form ────────────────────────────────────────────────────

function JobForm({
  mode,
  job,
  onClose,
  onSaved,
}: {
  mode: 'create' | 'edit'
  job: ScheduledJob | null
  onClose: () => void
  onSaved: () => void
}) {
  const isEdit = mode === 'edit' && job != null

  const [selectedFlow, setSelectedFlow] = useState(job?.flow_id ?? '')
  const [schedule, setSchedule] = useState<CronScheduleState>(() =>
    isEdit
      ? parseScheduleToState(job.cron_expr, job.interval_seconds)
      : defaultCronScheduleState(),
  )
  const [timezone, setTimezone] = useState(job?.timezone ?? 'UTC')
  const [isActive, setIsActive] = useState(job?.is_active ?? true)

  const { data: flows = [] } = useQuery({
    queryKey: ['flows'],
    queryFn: () => flowsApi.list(),
  })

  const built = buildScheduleFromState(schedule)
  const canSave =
    selectedFlow &&
    (built.cron_expr != null || built.interval_seconds != null)

  const mutation = useMutation({
    mutationFn: () => {
      const flowName =
        (flows as { flow_id: string; name?: string }[]).find(f => f.flow_id === selectedFlow)?.name
        || job?.flow_name
        || selectedFlow
      const body = {
        flow_id: selectedFlow,
        flow_name: flowName,
        cron_expr: built.cron_expr,
        interval_seconds: built.interval_seconds,
        timezone,
        is_active: isActive,
      }
      // POST upserts by flow_id and replaces cron vs interval cleanly
      return schedulerApi.createJob(body)
    },
    onSuccess: onSaved,
  })

  return (
    <div className="create-job-card">
      <div className="create-job-card__head">
        <span>{isEdit ? `Edit schedule — ${job.flow_name || job.flow_id}` : 'New Schedule'}</span>
        <button className="sched-close-btn" type="button" onClick={onClose}>×</button>
      </div>
      <div className="create-job-body">
        <div className="cj-row">
          <label>Flow</label>
          {isEdit ? (
            <div className="cj-flow-readonly">
              <div className="sched-flow-name">{job.flow_name || job.flow_id}</div>
              <div className="sched-flow-id">{job.flow_id}</div>
            </div>
          ) : (
            <select className="cj-select" value={selectedFlow} onChange={e => setSelectedFlow(e.target.value)}>
              <option value="">Select a flow…</option>
              {(flows as { flow_id: string; name?: string }[]).map((f) => (
                <option key={f.flow_id} value={f.flow_id}>{f.name || f.flow_id}</option>
              ))}
            </select>
          )}
        </div>

        <div className="cj-row">
          <label>Schedule</label>
          <CronScheduleBuilder value={schedule} onChange={setSchedule} />
        </div>

        <div className="cj-row">
          <label>Timezone</label>
          <input className="cj-input" value={timezone} onChange={e => setTimezone(e.target.value)} placeholder="UTC" />
        </div>

        <div className="cj-row cj-row--inline">
          <label>Start active</label>
          <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} />
        </div>

        {mutation.error && (
          <div className="cj-error">{(mutation.error as any).message}</div>
        )}

        <div className="cj-actions">
          <button className="sched-btn sched-btn--ghost" onClick={onClose}>Cancel</button>
          <button
            className="sched-btn sched-btn--primary"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !canSave}
          >
            {mutation.isPending ? 'Saving…' : isEdit ? 'Update schedule' : 'Save schedule'}
          </button>
        </div>
      </div>
    </div>
  )
}
