import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { flowsApi, runsApi } from '@/api/flows'
import { gatewayApi } from '@/api/gateway'
import { useAuthStore } from '@/store/authStore'
import {
  EmptyPanel,
  FlowStatusBadge,
  KpiGrid,
  PageHeader,
  SurfaceCard,
} from '@/components/ui/enterprise/PageChrome'
import '@/components/ui/enterprise/PageChrome.css'
import './DashboardPage.css'

const QUICK_LINKS = [
  {
    label: 'Monitor runs', desc: 'Live status, logs, and history', path: '/runs',
    svg: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" width="18" height="18"><polygon points="4,2 14,8 4,14" fill="none"/></svg>,
  },
  {
    label: 'Design a flow', desc: 'Open the visual flow designer', path: '/flows',
    svg: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" width="18" height="18"><circle cx="2.5" cy="8" r="1.5"/><circle cx="13.5" cy="4" r="1.5"/><circle cx="13.5" cy="12" r="1.5"/><polyline points="4,8 8,8 8,4 12,4"/><polyline points="8,8 8,12 12,12"/></svg>,
  },
  {
    label: 'Schedules', desc: 'Cron and interval automation', path: '/scheduler',
    svg: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" width="18" height="18"><circle cx="8" cy="8" r="6"/><polyline points="8,4.5 8,8 10.5,10.5"/></svg>,
  },
  {
    label: 'Connections', desc: 'Connector health and tests', path: '/connections',
    svg: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" width="18" height="18"><path d="M10 2l2 2-2 2"/><path d="M4 14l-2-2 2-2"/><path d="M12 4H6a2 2 0 00-2 2v4"/><path d="M4 12h6a2 2 0 002-2V6"/></svg>,
  },
] as const

export function DashboardPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const { data: flows = [] } = useQuery({ queryKey: ['flows'], queryFn: () => flowsApi.list() })
  const { data: runs = [] } = useQuery({
    queryKey: ['runs'],
    queryFn: () => runsApi.list(),
    refetchInterval: 30_000,
  })
  const { data: summary } = useQuery({
    queryKey: ['gateway-summary'],
    queryFn: () => gatewayApi.getSummary(),
    retry: false,
  })

  const deployed = flows.filter((f: { status: string }) => f.status === 'deployed').length
  const draft = flows.filter((f: { status: string }) => f.status === 'draft').length
  const failed = flows.filter((f: { status: string }) => f.status === 'failed').length

  type RunRow = { run_id: string; flow_id: string; status: string; started_at: string; rows_processed?: number }
  const flowById = Object.fromEntries(
    (flows as { flow_id: string; name?: string }[]).map((f) => [f.flow_id, f.name ?? f.flow_id])
  )
  const recentRuns = (runs as RunRow[])
    .slice()
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .slice(0, 8)

  function fmtRel(iso: string) {
    const diff = Date.now() - new Date(iso).getTime()
    if (diff < 60_000) return 'just now'
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
    return `${Math.floor(diff / 86_400_000)}d ago`
  }

  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })

  return (
    <div className="page-shell ep-page dashboard">
      <PageHeader
        meta={today}
        title="Operations overview"
        description={
          <>
            Signed in as <strong>{user?.email}</strong>
            {user?.role && (
              <span className={`ep-role ep-role--${user.role}`}>{user.role}</span>
            )}
          </>
        }
        actions={
          <>
            <button type="button" className="btn btn--secondary" onClick={() => navigate('/runs')}>
              View runs
            </button>
            <button type="button" className="btn btn--primary" onClick={() => navigate('/flows')}>
              New flow
            </button>
          </>
        }
      />

      <KpiGrid
        items={[
          { id: 'flows', label: 'Integration flows', value: flows.length, hint: `${deployed} deployed · ${draft} draft`, onClick: () => navigate('/flows') },
          { id: 'deployed', label: 'Production ready', value: deployed, tone: 'accent' as const, hint: 'Deployed flows', onClick: () => navigate('/flows') },
          { id: 'failed', label: 'Needs attention', value: failed, tone: failed > 0 ? 'danger' as const : 'default' as const, hint: failed > 0 ? 'Click to view failing flows' : 'No issues', onClick: failed > 0 ? () => navigate('/flows') : undefined },
          { id: 'api', label: 'API products', value: summary?.total_products ?? '—', hint: 'Gateway catalog' },
          { id: 'req', label: 'Gateway traffic', value: summary?.total_requests ?? '—', hint: 'Requests (period)' },
        ]}
      />

      <div className="ep-layout-split">
        <SurfaceCard
          title="Recent flows"
          subtitle="Open a flow to edit, validate, or run"
          action={
            <button type="button" className="link-btn" onClick={() => navigate('/flows')}>
              All flows →
            </button>
          }
          noPadding
        >
          {flows.length === 0 ? (
            <EmptyPanel
              icon="◇"
              title="No flows yet"
              description="Create an integration flow to move data between systems."
              action={
                <button type="button" className="btn btn--primary" onClick={() => navigate('/flows')}>
                  Create first flow
                </button>
              }
            />
          ) : (
            <div className="ep-table-wrap">
              <table className="ep-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Identifier</th>
                  </tr>
                </thead>
                <tbody>
                  {flows.slice(0, 10).map((f: { flow_id: string; name?: string; status: string }) => (
                    <tr
                      key={f.flow_id}
                      className="ep-table__row"
                      onClick={() => navigate(`/flows/${f.flow_id}`)}
                    >
                      <td>
                        <div className="ep-table__primary">{f.name || f.flow_id}</div>
                      </td>
                      <td><FlowStatusBadge status={f.status} /></td>
                      <td className="ep-table__mono">{f.flow_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SurfaceCard>

        <SurfaceCard title="Shortcuts" subtitle="Common operator tasks">
          <div className="ep-quick-grid">
            {QUICK_LINKS.map((q) => (
              <button
                key={q.path}
                type="button"
                className="ep-quick-link"
                onClick={() => navigate(q.path)}
              >
                <span className="ep-quick-link__icon">{q.svg}</span>
                <div>
                  <div className="ep-quick-link__label">{q.label}</div>
                  <div className="ep-quick-link__desc">{q.desc}</div>
                </div>
              </button>
            ))}
          </div>
        </SurfaceCard>
      </div>

      <SurfaceCard
        title="Recent activity"
        subtitle="Last 8 runs across all flows — refreshes every 30 s"
        action={
          <button type="button" className="link-btn" onClick={() => navigate('/runs')}>
            All runs →
          </button>
        }
        noPadding
      >
        {recentRuns.length === 0 ? (
          <EmptyPanel
            icon="▶"
            title="No runs yet"
            description="Run a flow to see execution history here."
          />
        ) : (
          <div className="ep-table-wrap">
            <table className="ep-table">
              <thead>
                <tr>
                  <th>Flow</th>
                  <th>Status</th>
                  <th>Rows</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((r) => {
                  const tone = r.status === 'success' ? 'pass' : r.status === 'failed' ? 'fail' : 'warn'
                  const icon = r.status === 'success' ? '✓' : r.status === 'failed' ? '✕' : '⟳'
                  return (
                    <tr
                      key={r.run_id}
                      className="ep-table__row"
                      onClick={() => navigate('/runs')}
                    >
                      <td>
                        <div className="ep-table__primary">{flowById[r.flow_id] ?? r.flow_id}</div>
                        <div className="ep-table__mono ep-table__secondary">{r.run_id}</div>
                      </td>
                      <td>
                        <span className={`dash-run-badge dash-run-badge--${tone}`}>
                          {icon} {r.status}
                        </span>
                      </td>
                      <td className="ep-table__mono">{r.rows_processed?.toLocaleString() ?? '—'}</td>
                      <td className="flows-table__date">{fmtRel(r.started_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>
    </div>
  )
}
