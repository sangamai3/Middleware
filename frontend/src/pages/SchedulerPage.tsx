import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { schedulerApi, type ScheduledJob } from '@/api/scheduler'
import { flowsApi } from '@/api/flows'
import './SchedulerPage.css'

// Common cron presets
const CRON_PRESETS = [
  { label: 'Every 5 minutes', value: '*/5 * * * *' },
  { label: 'Every 15 minutes', value: '*/15 * * * *' },
  { label: 'Every 30 minutes', value: '*/30 * * * *' },
  { label: 'Every hour', value: '0 * * * *' },
  { label: 'Daily at midnight', value: '0 0 * * *' },
  { label: 'Daily at 9 AM', value: '0 9 * * *' },
  { label: 'Weekdays at 8 AM', value: '0 8 * * 1-5' },
  { label: 'Weekly on Monday', value: '0 9 * * 1' },
  { label: 'Monthly on 1st', value: '0 9 1 * *' },
  { label: 'Custom…', value: '__custom__' },
]

export function SchedulerPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)

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
          <p className="scheduler__sub">Schedule flows to run on cron or interval triggers.</p>
        </div>
        <button className="sched-btn sched-btn--primary" onClick={() => setShowCreate(true)}>
          + Schedule flow
        </button>
      </div>

      {showCreate && (
        <CreateJobForm
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); qc.invalidateQueries({ queryKey: ['scheduler-jobs'] }) }}
        />
      )}

      {isLoading ? (
        <div className="sched-loading">Loading schedules…</div>
      ) : jobs.length === 0 && !showCreate ? (
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

// ── Create job form ───────────────────────────────────────────────────────────

function CreateJobForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [selectedFlow, setSelectedFlow] = useState('')
  const [triggerMode, setTriggerMode] = useState<'cron' | 'interval'>('cron')
  const [cronPreset, setCronPreset] = useState('0 * * * *')
  const [customCron, setCustomCron] = useState('')
  const [intervalSecs, setIntervalSecs] = useState('3600')
  const [timezone, setTimezone] = useState('UTC')
  const [isActive, setIsActive] = useState(true)

  const { data: flows = [] } = useQuery({
    queryKey: ['flows'],
    queryFn: () => flowsApi.list(),
  })

  const isCustom = cronPreset === '__custom__'
  const effectiveCron = isCustom ? customCron : cronPreset

  const mutation = useMutation({
    mutationFn: () => {
      const flowName = (flows as any[]).find(f => f.flow_id === selectedFlow)?.name || selectedFlow
      return schedulerApi.createJob({
        flow_id: selectedFlow,
        flow_name: flowName,
        cron_expr: triggerMode === 'cron' ? effectiveCron : null,
        interval_seconds: triggerMode === 'interval' ? parseInt(intervalSecs, 10) : null,
        timezone,
        is_active: isActive,
      })
    },
    onSuccess: onCreated,
  })

  return (
    <div className="create-job-card">
      <div className="create-job-card__head">
        <span>New Schedule</span>
        <button className="sched-close-btn" onClick={onClose}>×</button>
      </div>
      <div className="create-job-body">
        <div className="cj-row">
          <label>Flow</label>
          <select className="cj-select" value={selectedFlow} onChange={e => setSelectedFlow(e.target.value)}>
            <option value="">Select a flow…</option>
            {(flows as any[]).map((f: any) => (
              <option key={f.flow_id} value={f.flow_id}>{f.name || f.flow_id}</option>
            ))}
          </select>
        </div>

        <div className="cj-row">
          <label>Trigger type</label>
          <div className="cj-toggle">
            <button className={`cj-toggle-btn${triggerMode === 'cron' ? ' cj-toggle-btn--active' : ''}`} onClick={() => setTriggerMode('cron')}>Cron</button>
            <button className={`cj-toggle-btn${triggerMode === 'interval' ? ' cj-toggle-btn--active' : ''}`} onClick={() => setTriggerMode('interval')}>Interval</button>
          </div>
        </div>

        {triggerMode === 'cron' && (
          <>
            <div className="cj-row">
              <label>Preset</label>
              <select className="cj-select" value={cronPreset} onChange={e => setCronPreset(e.target.value)}>
                {CRON_PRESETS.map(p => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            {isCustom && (
              <div className="cj-row">
                <label>Cron expression</label>
                <input
                  className="cj-input cj-input--mono"
                  value={customCron}
                  onChange={e => setCustomCron(e.target.value)}
                  placeholder="0 9 * * 1-5"
                />
                <div className="cj-hint">minute hour dom month dow</div>
              </div>
            )}
            {!isCustom && (
              <div className="cj-preview">
                <span className="cj-preview__label">Expression:</span>
                <code className="cj-preview__expr">{cronPreset}</code>
              </div>
            )}
          </>
        )}

        {triggerMode === 'interval' && (
          <div className="cj-row">
            <label>Interval (seconds)</label>
            <input
              className="cj-input"
              type="number"
              min="60"
              value={intervalSecs}
              onChange={e => setIntervalSecs(e.target.value)}
            />
            <div className="cj-hint">
              {(() => {
                const s = parseInt(intervalSecs, 10) || 0
                if (s >= 3600) return `Every ${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
                if (s >= 60) return `Every ${Math.floor(s / 60)}m ${s % 60}s`
                return `Every ${s}s`
              })()}
            </div>
          </div>
        )}

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
            disabled={mutation.isPending || !selectedFlow || (triggerMode === 'cron' && isCustom && !customCron.trim())}
          >
            {mutation.isPending ? 'Saving…' : 'Save schedule'}
          </button>
        </div>
      </div>
    </div>
  )
}
