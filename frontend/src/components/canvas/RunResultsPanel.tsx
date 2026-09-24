import { Link } from 'react-router-dom'
import { useCanvasStore } from '@/store/canvasStore'
import { stepTimelineTitle } from '@/lib/stepDisplay'
import type { ExecutionRun, StepExecution } from '@/types'
import './RunResultsPanel.css'

function statusClass(s: string) {
  if (s === 'success') return 'run-results__badge--pass'
  if (s === 'failed' || s === 'timed_out') return 'run-results__badge--fail'
  if (s === 'running') return 'run-results__badge--run'
  return 'run-results__badge--muted'
}

function runDuration(run: ExecutionRun): string {
  if (!run.started_at) return '—'
  const end = run.ended_at ? new Date(run.ended_at).getTime() : Date.now()
  const start = new Date(run.started_at).getTime()
  const ms = end - start
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

function stepDuration(s: StepExecution): string {
  if (s.duration_ms != null) {
    return s.duration_ms < 1000 ? `${s.duration_ms}ms` : `${(s.duration_ms / 1000).toFixed(1)}s`
  }
  if (!s.started_at || !s.ended_at) return '—'
  const ms = new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

export function RunResultsPanel() {
  const {
    nodes,
    isRunning,
    runId,
    runResult,
    runPanelOpen,
    setRunPanelOpen,
  } = useCanvasStore()

  const showBar = isRunning || runResult || runId

  if (!showBar) return null

  const status = isRunning ? 'running' : (runResult?.status ?? 'pending')
  const totalRows = runResult?.rows_processed ?? nodes.reduce((n, node) => {
    const out = node.data.rowsOut
    return typeof out === 'number' ? Math.max(n, out) : n
  }, 0)

  if (!runPanelOpen) {
    return (
      <div className="run-results run-results--collapsed">
        <button
          type="button"
          className="run-results__expand"
          onClick={() => setRunPanelOpen(true)}
        >
          Run results
          {status && (
            <span className={`run-results__badge ${statusClass(status)}`}>{status}</span>
          )}
        </button>
      </div>
    )
  }

  const steps = runResult?.steps?.length
    ? runResult.steps
    : nodes
        .filter((n) => n.data.status)
        .map((n) => ({
          step_id: n.id,
          step_type: String(n.data.stepType),
          step_label: String(n.data.label ?? ''),
          status: n.data.status as StepExecution['status'],
          rows_out: typeof n.data.rowsOut === 'number' ? n.data.rowsOut : 0,
          duration_ms: null,
          started_at: null,
          ended_at: null,
          rows_in: 0,
          rows_failed: 0,
          error_type: null,
          error_message: typeof n.data.error === 'string' ? n.data.error : null,
          retry_count: 0,
        }))

  return (
    <div className="run-results">
      <div className="run-results__header">
        <div className="run-results__title-row">
          <span className="run-results__title">Run results</span>
          <span className={`run-results__badge ${statusClass(status)}`}>{status}</span>
          {isRunning && <span className="run-results__live">Live</span>}
        </div>
        <div className="run-results__summary">
          {runId && (
            <span className="run-results__meta" title={runId}>
              Run {runId.slice(0, 8)}…
            </span>
          )}
          {runResult && (
            <>
              <span className="run-results__meta">{runDuration(runResult)}</span>
              <span className="run-results__meta">{totalRows.toLocaleString()} rows processed</span>
            </>
          )}
          {runId && !isRunning && (
            <Link className="run-results__link" to="/runs">
              Open in Runs →
            </Link>
          )}
        </div>
        <button
          type="button"
          className="run-results__collapse"
          onClick={() => setRunPanelOpen(false)}
          aria-label="Collapse run results"
        >
          ▾
        </button>
      </div>

      {runResult?.error_message && (
        <div className="run-results__error">{runResult.error_message}</div>
      )}

      <div className="run-results__steps">
        {steps.length === 0 && isRunning && (
          <div className="run-results__empty">Executing flow…</div>
        )}
        {steps.map((step) => {
          const label =
            step.step_label?.trim() ||
            stepTimelineTitle(step as StepExecution)
          const nodeLabel = nodes.find((n) => n.id === step.step_id)?.data.label
          const title = nodeLabel && nodeLabel !== label ? `${label} (${step.step_id})` : label
          return (
            <div key={step.step_id} className="run-results__step">
              <span className="run-results__step-name" title={step.step_id}>{title}</span>
              <span className={`run-results__badge run-results__badge--sm ${statusClass(step.status)}`}>
                {step.status}
              </span>
              {step.rows_out != null && step.rows_out > 0 && (
                <span className="run-results__step-rows">{step.rows_out} rows</span>
              )}
              <span className="run-results__step-dur">{stepDuration(step as StepExecution)}</span>
              {step.error_message && (
                <span className="run-results__step-err" title={step.error_message}>
                  {step.error_message.slice(0, 80)}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
