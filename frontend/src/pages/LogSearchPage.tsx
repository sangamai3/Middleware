import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { insightsApi, LogEntry } from '@/api/insights'
import './LogSearchPage.css'

const LEVELS = ['ALL', 'INFO', 'WARN', 'ERROR', 'DEBUG']
const PAGE_SIZE = 100

function highlight(text: string, q: string): React.ReactNode {
  if (!q) return text
  const idx = text.toLowerCase().indexOf(q.toLowerCase())
  if (idx === -1) return text
  return (
    <>
      {text.slice(0, idx)}
      <mark className="log-hl">{text.slice(idx, idx + q.length)}</mark>
      {text.slice(idx + q.length)}
    </>
  )
}

function LevelBadge({ level }: { level: string }) {
  const cls = level === 'ERROR' ? 'lvl--error' : level === 'WARN' ? 'lvl--warn' : level === 'DEBUG' ? 'lvl--debug' : 'lvl--info'
  return <span className={`lvl-badge ${cls}`}>{level}</span>
}

export function LogSearchPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [level, setLevel] = useState('ALL')
  const [flowId, setFlowId] = useState('')
  const [runId, setRunId] = useState('')
  const [offset, setOffset] = useState(0)

  // Simple debounce
  const handleQChange = useCallback((val: string) => {
    setQ(val)
    clearTimeout((handleQChange as any)._t)
    ;(handleQChange as any)._t = setTimeout(() => {
      setDebouncedQ(val)
      setOffset(0)
    }, 300)
  }, [])

  const params = {
    q: debouncedQ || undefined,
    level: level !== 'ALL' ? level : undefined,
    flow_id: flowId || undefined,
    run_id: runId || undefined,
    limit: PAGE_SIZE,
    offset,
  }

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['log-search', params],
    queryFn: () => insightsApi.searchLogs(params),
    enabled: !!(debouncedQ || flowId || runId || level !== 'ALL'),
    placeholderData: undefined,
  })

  const total = data?.total ?? 0
  const logs = data?.logs ?? []

  return (
    <div className="log-search-page">
      <div className="log-search-page__header">
        <h1 className="log-search-page__title">Log Search</h1>
      </div>

      {/* Search bar */}
      <div className="log-search-bar">
        <input
          className="log-search-input"
          type="text"
          placeholder="Search log messages…"
          value={q}
          onChange={e => handleQChange(e.target.value)}
        />
      </div>

      {/* Filters */}
      <div className="log-filters">
        <select
          className="log-filter-sel"
          value={level}
          onChange={e => { setLevel(e.target.value); setOffset(0) }}
        >
          {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <input
          className="log-filter-input"
          type="text"
          placeholder="Flow ID…"
          value={flowId}
          onChange={e => { setFlowId(e.target.value); setOffset(0) }}
        />
        <input
          className="log-filter-input"
          type="text"
          placeholder="Run ID…"
          value={runId}
          onChange={e => { setRunId(e.target.value); setOffset(0) }}
        />
        {(total > 0) && (
          <span className="log-result-count">{total.toLocaleString()} results</span>
        )}
      </div>

      {/* Results */}
      <div className="log-results">
        {!debouncedQ && !flowId && !runId && level === 'ALL' ? (
          <p className="log-empty">Enter a search term or filter to begin.</p>
        ) : isLoading || isFetching ? (
          <p className="log-empty">Searching…</p>
        ) : logs.length === 0 ? (
          <p className="log-empty">No logs matching your query.</p>
        ) : (
          <>
            {logs.map((lg: LogEntry) => (
              <div
                key={lg.id}
                className="log-row"
                onClick={() => {
                  if (lg.flow_id && lg.run_id) {
                    navigate(`/insights/flows/${lg.flow_id}?run=${lg.run_id}`)
                  }
                }}
              >
                <span className="log-row__ts">
                  {lg.timestamp ? new Date(lg.timestamp).toLocaleTimeString() : ''}
                </span>
                <LevelBadge level={lg.level} />
                <span className="log-row__flow">{lg.flow_id}</span>
                {lg.step_id && <span className="log-row__step">{lg.step_id}</span>}
                <span className="log-row__msg">{highlight(lg.message, debouncedQ)}</span>
              </div>
            ))}

            {/* Pagination */}
            <div className="log-pagination">
              <button
                className="log-page-btn"
                disabled={offset === 0}
                onClick={() => setOffset(o => Math.max(0, o - PAGE_SIZE))}
              >
                ← Prev
              </button>
              <span className="log-page-info">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <button
                className="log-page-btn"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset(o => o + PAGE_SIZE)}
              >
                Next →
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
