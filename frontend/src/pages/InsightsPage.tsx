import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { insightsApi, FlowInsight } from '@/api/insights'
import './InsightsPage.css'

const TIME_RANGES = [
  { label: '1h', from: () => new Date(Date.now() - 3600_000).toISOString() },
  { label: '6h', from: () => new Date(Date.now() - 6 * 3600_000).toISOString() },
  { label: '24h', from: () => new Date(Date.now() - 24 * 3600_000).toISOString() },
  { label: '7d', from: () => new Date(Date.now() - 7 * 86400_000).toISOString() },
]

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === 'success' || status === 'completed'
      ? 'badge--pass'
      : status === 'running'
      ? 'badge--run'
      : 'badge--fail'
  return <span className={`badge ${cls}`}>{status}</span>
}

function fmtDur(ms: number | null): string {
  if (!ms) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function fmtRel(iso: string | null): string {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return 'just now'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`
  return `${Math.floor(diff / 86400_000)}d ago`
}

export function InsightsPage() {
  const navigate = useNavigate()
  const [rangeIdx, setRangeIdx] = useState(2) // default 24h

  const from_dt = TIME_RANGES[rangeIdx].from()

  const { data: overview } = useQuery({
    queryKey: ['insights-overview'],
    queryFn: () => insightsApi.overview(),
    refetchInterval: 30_000,
  })

  const { data: flows = [], isLoading } = useQuery({
    queryKey: ['insights-flows', rangeIdx],
    queryFn: () => insightsApi.flows({ from_dt }),
    refetchInterval: 30_000,
  })

  return (
    <div className="insights-page">
      <div className="insights-page__header">
        <div>
          <h1 className="insights-page__title">App Insights</h1>
          <p className="insights-page__sub">Observability across all flows</p>
        </div>
        <div className="insights-range-tabs">
          {TIME_RANGES.map((r, i) => (
            <button
              key={r.label}
              className={`range-tab${rangeIdx === i ? ' range-tab--active' : ''}`}
              onClick={() => setRangeIdx(i)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary tiles */}
      {overview && (
        <div className="insights-tiles">
          <div className="insights-tile">
            <span className="insights-tile__label">Flows Monitored</span>
            <span className="insights-tile__value">{overview.total_flows}</span>
          </div>
          <div className="insights-tile">
            <span className="insights-tile__label">Runs Today</span>
            <span className="insights-tile__value">{overview.runs_today}</span>
          </div>
          <div className="insights-tile insights-tile--warn">
            <span className="insights-tile__label">Error Rate</span>
            <span className="insights-tile__value">{overview.error_rate}%</span>
          </div>
          <div className="insights-tile">
            <span className="insights-tile__label">Avg Duration</span>
            <span className="insights-tile__value">{fmtDur(overview.avg_duration_ms)}</span>
          </div>
        </div>
      )}

      {/* Flow health table */}
      <div className="insights-section">
        <h2 className="insights-section__title">Flow Health</h2>
        {isLoading ? (
          <p className="insights-empty">Loading…</p>
        ) : flows.length === 0 ? (
          <p className="insights-empty">No flow runs in the selected range.</p>
        ) : (
          <table className="insights-table">
            <thead>
              <tr>
                <th>Flow</th>
                <th>Runs</th>
                <th>Errors</th>
                <th>Error Rate</th>
                <th>Avg Duration</th>
                <th>Last Run</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {flows.map((f: FlowInsight) => (
                <tr
                  key={f.flow_id}
                  className="insights-table__row"
                  onClick={() => navigate(`/insights/flows/${f.flow_id}`)}
                >
                  <td className="insights-table__name">{f.flow_name}</td>
                  <td>{f.run_count}</td>
                  <td>{f.error_count > 0 ? <span className="err-chip">{f.error_count}</span> : 0}</td>
                  <td>
                    <span className={f.error_rate > 0 ? 'rate--bad' : 'rate--ok'}>
                      {f.error_rate}%
                    </span>
                  </td>
                  <td>{fmtDur(f.avg_duration_ms)}</td>
                  <td className="insights-table__rel">{fmtRel(f.last_run_at)}</td>
                  <td><StatusBadge status={f.last_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Quick links */}
      <div className="insights-links">
        <button className="insights-link-btn" onClick={() => navigate('/logs')}>
          🔍 Search Logs
        </button>
        <button className="insights-link-btn" onClick={() => navigate('/events')}>
          📋 Business Events
        </button>
      </div>
    </div>
  )
}
