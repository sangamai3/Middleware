import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { insightsApi, BusinessEvent } from '@/api/insights'
import './BusinessEventsPage.css'

const PAGE_SIZE = 50

export function BusinessEventsPage() {
  const navigate = useNavigate()
  const [flowId, setFlowId] = useState('')
  const [eventName, setEventName] = useState('')
  const [correlationId, setCorrelationId] = useState('')
  const [offset, setOffset] = useState(0)
  const [expanded, setExpanded] = useState<number | null>(null)

  const params = {
    flow_id: flowId || undefined,
    event_name: eventName || undefined,
    correlation_id: correlationId || undefined,
    limit: PAGE_SIZE,
    offset,
  }

  const { data, isLoading } = useQuery({
    queryKey: ['business-events', params],
    queryFn: () => insightsApi.businessEvents(params),
    refetchInterval: 30_000,
  })

  const total = data?.total ?? 0
  const events = data?.events ?? []

  function fmtTs(iso: string | null): string {
    if (!iso) return '—'
    return new Date(iso).toLocaleString()
  }

  return (
    <div className="bev-page">
      <div className="bev-header">
        <h1 className="bev-title">Business Events</h1>
        <p className="bev-sub">Custom domain events emitted by flow steps</p>
      </div>

      {/* Filters */}
      <div className="bev-filters">
        <input
          className="bev-filter-input"
          type="text"
          placeholder="Event name…"
          value={eventName}
          onChange={e => { setEventName(e.target.value); setOffset(0) }}
        />
        <input
          className="bev-filter-input"
          type="text"
          placeholder="Flow ID…"
          value={flowId}
          onChange={e => { setFlowId(e.target.value); setOffset(0) }}
        />
        <input
          className="bev-filter-input bev-filter-input--wide"
          type="text"
          placeholder="Correlation ID…"
          value={correlationId}
          onChange={e => { setCorrelationId(e.target.value); setOffset(0) }}
        />
        {total > 0 && <span className="bev-count">{total.toLocaleString()} events</span>}
      </div>

      {/* Table */}
      {isLoading ? (
        <p className="bev-empty">Loading…</p>
      ) : events.length === 0 ? (
        <p className="bev-empty">No business events found.</p>
      ) : (
        <div className="bev-table-wrap">
          <table className="bev-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Flow</th>
                <th>Run ID</th>
                <th>Correlation</th>
                <th>Time</th>
                <th>Payload</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev: BusinessEvent) => (
                <>
                  <tr
                    key={ev.id}
                    className="bev-row"
                    onClick={() => setExpanded(expanded === ev.id ? null : ev.id)}
                  >
                    <td className="bev-row__name">{ev.event_name}</td>
                    <td
                      className="bev-row__flow"
                      onClick={e => { e.stopPropagation(); navigate(`/insights/flows/${ev.flow_id}`) }}
                    >
                      {ev.flow_id}
                    </td>
                    <td className="bev-row__run">{ev.run_id.slice(0, 8)}…</td>
                    <td className="bev-row__corr">{ev.correlation_id ? ev.correlation_id.slice(0, 8) + '…' : '—'}</td>
                    <td className="bev-row__ts">{fmtTs(ev.occurred_at)}</td>
                    <td className="bev-row__expand">{expanded === ev.id ? '▲' : '▼'}</td>
                  </tr>
                  {expanded === ev.id && (
                    <tr key={`${ev.id}-payload`} className="bev-payload-row">
                      <td colSpan={6}>
                        <pre className="bev-payload">{JSON.stringify(ev.payload, null, 2)}</pre>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>

          <div className="bev-pagination">
            <button
              className="bev-page-btn"
              disabled={offset === 0}
              onClick={() => setOffset(o => Math.max(0, o - PAGE_SIZE))}
            >
              ← Prev
            </button>
            <span className="bev-page-info">{offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}</span>
            <button
              className="bev-page-btn"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(o => o + PAGE_SIZE)}
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
