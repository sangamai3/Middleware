import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi, type AdminUser, type AuditEntry } from '@/api/admin'
import './AdminPage.css'

type AdminTab = 'users' | 'audit' | 'system'

export function AdminPage() {
  const [tab, setTab] = useState<AdminTab>('users')

  return (
    <div className="admin">
      <div className="admin__header">
        <h1 className="admin__title">Admin Portal</h1>
        <div className="tab-bar">
          <button className={`tab${tab === 'users' ? ' tab--active' : ''}`} onClick={() => setTab('users')}>Users</button>
          <button className={`tab${tab === 'audit' ? ' tab--active' : ''}`} onClick={() => setTab('audit')}>Audit Log</button>
          <button className={`tab${tab === 'system' ? ' tab--active' : ''}`} onClick={() => setTab('system')}>System</button>
        </div>
      </div>

      {tab === 'users' && <UsersTab />}
      {tab === 'audit' && <AuditTab />}
      {tab === 'system' && <SystemTab />}
    </div>
  )
}

// ── Users ─────────────────────────────────────────────────────────────────────

const ROLES = ['admin', 'developer', 'operator', 'viewer'] as const

function UsersTab() {
  const qc = useQueryClient()
  const { data: users = [], isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => adminApi.listUsers(),
  })

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      adminApi.updateUserRole(userId, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  const deactivateMutation = useMutation({
    mutationFn: (userId: string) => adminApi.deactivateUser(userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  if (isLoading) return <div className="admin-loading">Loading users…</div>

  return (
    <div className="admin-section">
      <div className="admin-section__head">
        <span className="admin-count">{users.length} user{users.length !== 1 ? 's' : ''}</span>
      </div>
      <table className="admin-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Role</th>
            <th>Status</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u: AdminUser) => (
            <tr key={u.user_id}>
              <td>
                <div className="admin-user">
                  <div className="admin-user__name">{u.email}</div>
                </div>
              </td>
              <td>
                <select
                  className={`role-select role-select--${u.role}`}
                  value={u.role}
                  onChange={e => roleMutation.mutate({ userId: u.user_id, role: e.target.value })}
                >
                  {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </td>
              <td>
                <span className={`status-badge${u.is_active ? ' status-badge--active' : ' status-badge--inactive'}`}>
                  {u.is_active ? 'active' : 'deactivated'}
                </span>
              </td>
              <td className="admin-date">{new Date(u.created_at).toLocaleDateString()}</td>
              <td>
                {u.is_active && (
                  <button
                    className="admin-danger-btn"
                    onClick={() => deactivateMutation.mutate(u.user_id)}
                    disabled={deactivateMutation.isPending}
                  >
                    Deactivate
                  </button>
                )}
              </td>
            </tr>
          ))}
          {users.length === 0 && (
            <tr><td colSpan={5} className="admin-empty">No users found.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ── Audit log ─────────────────────────────────────────────────────────────────

function AuditTab() {
  const [chainValid, setChainValid] = useState<boolean | null>(null)
  const [verifying, setVerifying] = useState(false)

  const { data: entries = [] } = useQuery({
    queryKey: ['admin-audit'],
    queryFn: () => adminApi.listAuditLog(),
  })

  async function verifyChain() {
    setVerifying(true)
    try {
      const result = await adminApi.verifyAuditChain()
      setChainValid(result.valid)
    } catch {
      setChainValid(false)
    } finally {
      setVerifying(false)
    }
  }

  return (
    <div className="admin-section">
      <div className="admin-section__head">
        <span className="admin-count">{entries.length} entries</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {chainValid !== null && (
            <span className={`chain-badge${chainValid ? ' chain-badge--valid' : ' chain-badge--invalid'}`}>
              {chainValid ? '✓ Chain valid' : '✗ Chain broken'}
            </span>
          )}
          <button className="admin-btn" onClick={verifyChain} disabled={verifying}>
            {verifying ? 'Verifying…' : 'Verify chain'}
          </button>
        </div>
      </div>
      <table className="admin-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Actor</th>
            <th>Action</th>
            <th>Resource</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e: AuditEntry) => (
            <tr key={e.id}>
              <td className="admin-date">{new Date(e.created_at).toLocaleString()}</td>
              <td className="admin-mono">{e.actor_id}</td>
              <td><span className="action-badge">{e.action}</span></td>
              <td className="admin-mono">{e.resource_type}/{e.resource_id}</td>
              <td className="admin-detail">{e.entry_hash.slice(0, 12)}…</td>
            </tr>
          ))}
          {entries.length === 0 && (
            <tr><td colSpan={5} className="admin-empty">No audit entries yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ── System stats ──────────────────────────────────────────────────────────────

function SystemTab() {
  const { data: stats, isLoading, refetch } = useQuery({
    queryKey: ['admin-system'],
    queryFn: () => adminApi.systemStats(),
    retry: false,
  })

  if (isLoading) return <div className="admin-loading">Loading stats…</div>
  if (!stats) return <div className="admin-loading">Stats unavailable.</div>

  return (
    <div className="admin-section">
      <div className="admin-section__head">
        <span className="admin-count">System health</span>
        <button className="admin-btn" onClick={() => refetch()}>Refresh</button>
      </div>
      <div className="stats-grid">
        <StatCard label="Users" value={stats.user_count} />
        <StatCard label="Flows" value={stats.flow_count} />
        <StatCard label="Connectors" value={stats.connector_count} />
        <StatCard label="Runs (24h)" value={stats.run_count_24h} />
        <StatCard label="Error Rate (24h)" value={+(stats.error_rate_24h * 100).toFixed(1)} />
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-card">
      <div className="stat-card__value">{value.toLocaleString()}</div>
      <div className="stat-card__label">{label}</div>
    </div>
  )
}

