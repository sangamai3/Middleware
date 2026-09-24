import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { runsApi } from '@/api/flows'
import { api } from '@/api/client'
import type { ExecutionRun, StepExecution } from '@/types'
import { stepTimelineTitle } from '@/lib/stepDisplay'
import './RunsPage.css'

type RunSummary = { run_id: string; flow_id: string; status: string; started_at: string }

function statusClass(s: string) {
  return s === 'success' ? 'badge--pass' : s === 'failed' ? 'badge--fail' : s === 'running' ? 'badge--warn' : 'badge--muted'
}

function durationMs(run: ExecutionRun) {
  if (!run.started_at) return '—'
  const end = run.ended_at ? new Date(run.ended_at).getTime() : Date.now()
  const start = new Date(run.started_at).getTime()
  const ms = end - start
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

function stepDuration(s: StepExecution) {
  if (!s.started_at || !s.ended_at) return ''
  const ms = new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

function StepWaterfall({ steps }: { steps: StepExecution[] }) {
  if (!steps.length) return <div className="run-detail__empty">No steps recorded.</div>

  const start = Math.min(...steps.filter(s => s.started_at).map(s => new Date(s.started_at!).getTime()))
  const end = Math.max(...steps.filter(s => s.ended_at).map(s => new Date(s.ended_at!).getTime()))
  const total = end - start || 1

  return (
    <div className="waterfall">
      {steps.map((s) => {
        const sOff = s.started_at ? new Date(s.started_at).getTime() - start : 0
        const dur = s.started_at && s.ended_at
          ? new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()
          : 0
        const left = (sOff / total) * 100
        const width = Math.max((dur / total) * 100, 0.5)
        const title = stepTimelineTitle(s)
        return (
          <div key={s.step_id} className="waterfall__row">
            <div className="waterfall__label" title={s.step_id}>
              <span className="waterfall__label-title">{title}</span>
              <span className="waterfall__label-id">{s.step_id}</span>
            </div>
            <div className="waterfall__track">
              <div
                className={`waterfall__bar waterfall__bar--${s.status}`}
                style={{ left: `${left}%`, width: `${width}%` }}
                title={`${s.status} · ${stepDuration(s)}${s.rows_out != null ? ` · ${s.rows_out} rows` : ''}`}
              />
            </div>
            <div className="waterfall__meta">
              <span className={`badge ${statusClass(s.status)}`}>{s.status}</span>
              {s.rows_out != null && <span className="waterfall__rows">{s.rows_out} rows</span>}
              <span className="waterfall__dur">{stepDuration(s)}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

interface DebugResult {
  suggestion: string
  ai_powered: boolean
  ai_error?: string
  context?: string
}

function AiDebugPanel({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false)
  const mutation = useMutation({
    mutationFn: () => api.post<DebugResult>(`/runs/${runId}/debug`, {}),
  })

  if (!open) {
    return (
      <button className="ai-debug-trigger" onClick={() => { setOpen(true); mutation.mutate() }}>
        🔍 Debug with AI
      </button>
    )
  }

  return (
    <div className="ai-debug-panel">
      <div className="ai-debug-panel__head">
        <span>AI Debug Assistant {mutation.data?.ai_powered ? <span className="ai-badge">AI</span> : <span className="ai-badge ai-badge--rule">rule-based</span>}</span>
        <button className="ai-debug-close" onClick={() => setOpen(false)}>×</button>
      </div>
      {mutation.isPending && <div className="ai-debug-body ai-debug-body--loading">Analyzing failure…</div>}
      {mutation.isError && <div className="ai-debug-body ai-debug-body--error">Failed to fetch suggestion.</div>}
      {mutation.data && (
        <div className="ai-debug-body">
          <pre className="ai-debug-suggestion">{mutation.data.suggestion}</pre>
          {mutation.data.ai_error && (
            <div className="ai-debug-note">AI unavailable: {mutation.data.ai_error}</div>
          )}
        </div>
      )}
    </div>
  )
}

function RunDetail({ runId }: { runId: string }) {
  const { data: run, isLoading } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => runsApi.get(runId),
    refetchInterval: (q) => q.state.data?.status === 'running' ? 1500 : false,
  })

  if (isLoading) return <div className="run-detail__empty">Loading…</div>
  if (!run) return <div className="run-detail__empty">Not found.</div>

  const isFailed = run.status === 'failed' || run.status === 'timed_out'

  return (
    <div className="run-detail">
      <div className="run-detail__header">
        <div>
          <div className="run-detail__id">{run.run_id}</div>
          <div className="run-detail__meta">
            Flow: <b>{run.flow_name?.trim() || run.flow_id}</b>
            {run.flow_name?.trim() && run.flow_id !== run.flow_name && (
              <span className="run-detail__flow-id"> ({run.flow_id})</span>
            )}
            &nbsp;·&nbsp;Trigger: {run.trigger_type}
            {run.triggered_by && <>&nbsp;·&nbsp;{run.triggered_by}</>}
          </div>
        </div>
        <div className="run-detail__stats">
          <span className={`badge ${statusClass(run.status)}`}>{run.status}</span>
          <span className="run-detail__dur">{durationMs(run)}</span>
        </div>
      </div>

      {run.error_message && (
        <div className="run-detail__error">{run.error_message}</div>
      )}

      {isFailed && <AiDebugPanel runId={run.run_id} />}

      <div className="run-detail__section-title">Step timeline</div>
      <StepWaterfall steps={run.steps ?? []} />
    </div>
  )
}

export function RunsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: runs = [], isLoading } = useQuery<RunSummary[]>({
    queryKey: ['runs'],
    queryFn: () => runsApi.list(),
    refetchInterval: 3000,
  })

  return (
    <div className="runs-page">
      <div className="runs-page__sidebar">
        <div className="runs-page__title">Runs</div>
        {isLoading ? (
          <div className="runs-page__empty">Loading…</div>
        ) : runs.length === 0 ? (
          <div className="runs-page__empty">No runs yet.</div>
        ) : (
          <div className="runs-list">
            {runs.map((r) => (
              <div
                key={r.run_id}
                className={`runs-list__item${selectedId === r.run_id ? ' runs-list__item--active' : ''}`}
                onClick={() => setSelectedId(r.run_id)}
              >
                <div className="runs-list__flow">{r.flow_id}</div>
                <div className="runs-list__row">
                  <span className={`badge ${statusClass(r.status)}`}>{r.status}</span>
                </div>
                <div className="runs-list__time">{r.started_at ? new Date(r.started_at).toLocaleString() : '—'}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="runs-page__main">
        {selectedId
          ? <RunDetail runId={selectedId} />
          : <div className="runs-page__placeholder">Select a run to see its timeline.</div>
        }
      </div>
    </div>
  )
}
