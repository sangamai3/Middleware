import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { insightsApi, RunHistoryItem, StepDetail } from '@/api/insights'
import './FlowInsightsPage.css'

const TIME_RANGES = [
  { label: '1h', hours: 1 },
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
  { label: '7d', hours: 168 },
]

function StatusBadge({ status }: { status: string }) {
  const cls = status === 'success' ? 'badge--pass' : status === 'running' ? 'badge--run' : 'badge--fail'
  return <span className={`badge ${cls}`}>{status}</span>
}

function fmtDur(ms: number | null): string {
  if (!ms) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function fmtTs(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

function Waterfall({ steps }: { steps: StepDetail[] }) {
  const maxDur = Math.max(...steps.map(s => s.duration_ms || 0), 1)
  return (
    <div className="fi-waterfall">
      {steps.map(s => {
        const pct = Math.max(2, ((s.duration_ms || 0) / maxDur) * 100)
        const cls = s.status === 'success' ? 'fi-bar--ok' : s.status === 'failed' ? 'fi-bar--fail' : 'fi-bar--run'
        return (
          <div key={s.step_id} className="fi-waterfall__row">
            <span className="fi-waterfall__label">{s.step_id}</span>
            <div className="fi-waterfall__track">
              <div className={`fi-waterfall__bar ${cls}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="fi-waterfall__dur">{fmtDur(s.duration_ms)}</span>
          </div>
        )
      })}
    </div>
  )
}

export function FlowInsightsPage() {
  const { id: flowId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [rangeIdx, setRangeIdx] = useState(2)
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const limit = 20

  const from_dt = new Date(Date.now() - TIME_RANGES[rangeIdx].hours * 3600_000).toISOString()

  const { data: runData, isLoading } = useQuery({
    queryKey: ['flow-runs', flowId, rangeIdx, page],
    queryFn: () => insightsApi.flowRuns(flowId!, { from_dt, limit, offset: page * limit }),
    enabled: !!flowId,
  })

  const { data: runDetail } = useQuery({
    queryKey: ['run-detail', selectedRun],
    queryFn: () => insightsApi.runDetail(selectedRun!),
    enabled: !!selectedRun,
  })

  return (
    <div className="fi-page">
      <div className="fi-header">
        <button className="fi-back" onClick={() => navigate('/insights')}>← Insights</button>
        <div>
          <h1 className="fi-title">Flow: {flowId}</h1>
        </div>
        <div className="insights-range-tabs">
          {TIME_RANGES.map((r, i) => (
            <button
              key={r.label}
              className={`range-tab${rangeIdx === i ? ' range-tab--active' : ''}`}
              onClick={() => { setRangeIdx(i); setPage(0); setSelectedRun(null) }}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="fi-body">
        {/* Run history list */}
        <div className="fi-list">
          <div className="fi-list__head">
            <span className="fi-list__count">{runData?.total ?? 0} runs</span>
          </div>
          {isLoading ? (
            <p className="fi-empty">Loading…</p>
          ) : (runData?.runs ?? []).length === 0 ? (
            <p className="fi-empty">No runs in range.</p>
          ) : (
            <>
              {(runData?.runs ?? []).map((r: RunHistoryItem) => (
                <div
                  key={r.run_id}
                  className={`fi-run-item${selectedRun === r.run_id ? ' fi-run-item--active' : ''}`}
                  onClick={() => setSelectedRun(r.run_id)}
                >
                  <div className="fi-run-item__top">
                    <StatusBadge status={r.status} />
                    <span className="fi-run-item__dur">{fmtDur(r.duration_ms)}</span>
                  </div>
                  <div className="fi-run-item__id">{r.run_id.slice(0, 8)}…</div>
                  <div className="fi-run-item__ts">{fmtTs(r.started_at)}</div>
                  {r.rows_processed > 0 && (
                    <div className="fi-run-item__rows">{r.rows_processed} rows</div>
                  )}
                </div>
              ))}
              <div className="fi-pagination">
                <button disabled={page === 0} onClick={() => setPage(p => p - 1)} className="fi-page-btn">← Prev</button>
                <span className="fi-page-num">Page {page + 1}</span>
                <button
                  disabled={(page + 1) * limit >= (runData?.total ?? 0)}
                  onClick={() => setPage(p => p + 1)}
                  className="fi-page-btn"
                >
                  Next →
                </button>
              </div>
            </>
          )}
        </div>

        {/* Run detail panel */}
        <div className="fi-detail">
          {!selectedRun ? (
            <div className="fi-detail__placeholder">Select a run to inspect</div>
          ) : !runDetail ? (
            <div className="fi-detail__placeholder">Loading…</div>
          ) : (
            <>
              <div className="fi-detail__header">
                <div>
                  <div className="fi-detail__run-id">{runDetail.run_id}</div>
                  <div className="fi-detail__meta">
                    {runDetail.trigger_type} · {runDetail.triggered_by || 'system'} · {fmtTs(runDetail.started_at)}
                  </div>
                </div>
                <StatusBadge status={runDetail.status} />
              </div>

              {runDetail.correlation_id && (
                <div className="fi-corr-chip" title="Correlation ID">
                  🔗 {runDetail.correlation_id}
                </div>
              )}

              {runDetail.error_message && (
                <div className="fi-error-box">{runDetail.error_message}</div>
              )}

              {runDetail.steps.length > 0 && (
                <section className="fi-section">
                  <div className="fi-section__title">Step Waterfall</div>
                  <Waterfall steps={runDetail.steps} />
                </section>
              )}

              {runDetail.logs.length > 0 && (
                <section className="fi-section">
                  <div className="fi-section__title">Log Timeline</div>
                  <div className="fi-log-list">
                    {runDetail.logs.map((lg, i) => (
                      <div key={i} className={`fi-log-row fi-log-row--${lg.level.toLowerCase()}`}>
                        <span className="fi-log-ts">{lg.timestamp ? new Date(lg.timestamp).toLocaleTimeString() : ''}</span>
                        <span className={`fi-log-level fi-log-level--${lg.level.toLowerCase()}`}>{lg.level}</span>
                        <span className="fi-log-msg">{lg.message}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {runDetail.business_events.length > 0 && (
                <section className="fi-section">
                  <div className="fi-section__title">Business Events</div>
                  <div className="fi-biz-list">
                    {runDetail.business_events.map((ev, i) => (
                      <div key={i} className="fi-biz-row">
                        <span className="fi-biz-name">{ev.event_name}</span>
                        <span className="fi-biz-ts">{ev.occurred_at ? new Date(ev.occurred_at).toLocaleTimeString() : ''}</span>
                        <pre className="fi-biz-payload">{JSON.stringify(ev.payload, null, 2)}</pre>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
