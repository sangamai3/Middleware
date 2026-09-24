import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { flowsApi } from '@/api/flows'
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
  { icon: '▶', label: 'Monitor runs', desc: 'Live status, logs, and history', path: '/runs' },
  { icon: '◇', label: 'Design a flow', desc: 'Open the visual flow designer', path: '/flows' },
  { icon: '⏱', label: 'Schedules', desc: 'Cron and interval automation', path: '/scheduler' },
  { icon: '⎔', label: 'Connections', desc: 'Connector health and tests', path: '/connections' },
] as const

export function DashboardPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const { data: flows = [] } = useQuery({ queryKey: ['flows'], queryFn: () => flowsApi.list() })
  const { data: summary } = useQuery({
    queryKey: ['gateway-summary'],
    queryFn: () => gatewayApi.getSummary(),
    retry: false,
  })

  const deployed = flows.filter((f: { status: string }) => f.status === 'deployed').length
  const draft = flows.filter((f: { status: string }) => f.status === 'draft').length
  const failed = flows.filter((f: { status: string }) => f.status === 'failed').length

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
          { id: 'flows', label: 'Integration flows', value: flows.length, hint: `${deployed} deployed · ${draft} draft` },
          { id: 'deployed', label: 'Production ready', value: deployed, tone: 'accent', hint: 'Deployed flows' },
          { id: 'failed', label: 'Needs attention', value: failed, tone: failed > 0 ? 'danger' : 'default', hint: 'Failed validation or runs' },
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
                <span className="ep-quick-link__icon">{q.icon}</span>
                <div>
                  <div className="ep-quick-link__label">{q.label}</div>
                  <div className="ep-quick-link__desc">{q.desc}</div>
                </div>
              </button>
            ))}
          </div>
        </SurfaceCard>
      </div>
    </div>
  )
}
