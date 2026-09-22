import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { flowsApi } from '@/api/flows'
import { gatewayApi } from '@/api/gateway'
import { useAuthStore } from '@/store/authStore'
import './DashboardPage.css'

function StatTile({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: boolean }) {
  return (
    <div className={`stat-tile${accent ? ' stat-tile--accent' : ''}`}>
      <div className="stat-tile__value">{value}</div>
      <div className="stat-tile__label">{label}</div>
      {sub && <div className="stat-tile__sub">{sub}</div>}
    </div>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const { data: flows = [] } = useQuery({ queryKey: ['flows'], queryFn: () => flowsApi.list() })
  const { data: summary } = useQuery({
    queryKey: ['gateway-summary'],
    queryFn: () => gatewayApi.getSummary(),
    retry: false,
  })

  const deployedFlows = flows.filter((f: any) => f.status === 'deployed').length
  const errorFlows = flows.filter((f: any) => f.status === 'failed').length

  return (
    <div className="dashboard">
      <div className="dashboard__header">
        <div>
          <h1 className="dashboard__title">Dashboard</h1>
          <p className="dashboard__sub">
            Welcome back, <strong>{user?.email}</strong>
            <span className={`role-chip role-chip--${user?.role}`}>{user?.role}</span>
          </p>
        </div>
        <button className="btn btn--primary" onClick={() => navigate('/flows')}>
          + New Flow
        </button>
      </div>

      <div className="stat-grid">
        <StatTile label="Total Flows" value={flows.length} sub={`${deployedFlows} deployed`} />
        <StatTile label="Deployed" value={deployedFlows} accent />
        <StatTile label="Failed" value={errorFlows} />
        <StatTile label="API Products" value={summary?.total_products ?? '—'} />
        <StatTile label="Gateway Req/Day" value={summary?.total_requests ?? '—'} />
      </div>

      <div className="dashboard__panels">
        <section className="dash-panel">
          <div className="dash-panel__head">
            <h2 className="dash-panel__title">Flows</h2>
            <button className="link-btn" onClick={() => navigate('/flows')}>View all →</button>
          </div>
          {flows.length === 0
            ? <EmptyState label="No flows yet" action="Create your first flow" onAction={() => navigate('/flows')} />
            : (
              <table className="dash-table">
                <thead><tr><th>Name</th><th>Status</th><th>ID</th></tr></thead>
                <tbody>
                  {flows.slice(0, 8).map((f: any) => (
                    <tr key={f.flow_id} className="dash-table__row" onClick={() => navigate(`/flows/${f.flow_id}`)}>
                      <td className="dash-table__name">{f.name || f.flow_id}</td>
                      <td><span className={`status-pill status-pill--${f.status}`}>{f.status}</span></td>
                      <td className="dash-table__id">{f.flow_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </section>

        <section className="dash-panel">
          <div className="dash-panel__head">
            <h2 className="dash-panel__title">Quick Actions</h2>
          </div>
          <div className="quick-actions">
            <QuickAction icon="⚡" label="Run a flow" desc="Execute any deployed flow now" onClick={() => navigate('/runs')} />
            <QuickAction icon="🔌" label="Add connection" desc="Connect a new data source or destination" onClick={() => navigate('/connections')} />
            <QuickAction icon="🔑" label="Issue API key" desc="Create a gateway API product key" onClick={() => navigate('/gateway')} />
            <QuickAction icon="📊" label="View audit log" desc="Browse tamper-evident activity log" onClick={() => navigate('/admin')} />
          </div>
        </section>
      </div>
    </div>
  )
}

function QuickAction({ icon, label, desc, onClick }: { icon: string; label: string; desc: string; onClick: () => void }) {
  return (
    <button className="quick-action" onClick={onClick}>
      <span className="quick-action__icon">{icon}</span>
      <div>
        <div className="quick-action__label">{label}</div>
        <div className="quick-action__desc">{desc}</div>
      </div>
    </button>
  )
}

function EmptyState({ label, action, onAction }: { label: string; action: string; onAction: () => void }) {
  return (
    <div className="empty-state">
      <p className="empty-state__label">{label}</p>
      <button className="link-btn" onClick={onAction}>{action}</button>
    </div>
  )
}
