import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { connectorsApi, type ConnectorHealthEntry } from '@/api/connectors'
import type { ConnectorMeta } from '@/types'
import './ConnectionsPage.css'

function HealthBadge({ status }: { status?: 'available' | 'unavailable' | 'error' }) {
  if (!status) return null
  const cls = status === 'available' ? 'badge--pass' : 'badge--fail'
  const label = status === 'available' ? '● healthy' : `● ${status}`
  return <span className={`badge ${cls} health-badge`}>{label}</span>
}

function ConnectorCard({
  connector,
  health,
  onTest,
}: {
  connector: ConnectorMeta
  health?: ConnectorHealthEntry
  onTest: (id: string) => void
}) {
  return (
    <div className="connector-card">
      <div className="connector-card__header">
        <div className="connector-card__name">{connector.label}</div>
        <div className="connector-card__badges">
          <span className="badge badge--muted">{connector.family}</span>
          <HealthBadge status={health?.status} />
        </div>
      </div>
      <div className="connector-card__type">{connector.connector_id}</div>
      {connector.description && (
        <div className="connector-card__desc">{connector.description}</div>
      )}
      {health?.message && health.status !== 'available' && (
        <div className="connector-card__health-msg">{health.message}</div>
      )}
      <div className="connector-card__ops">
        {connector.operations.map(op => (
          <span key={op} className="badge badge--muted connector-card__op">{op}</span>
        ))}
      </div>
      <div className="connector-card__footer">
        <button
          className="btn btn--ghost connector-card__test"
          onClick={() => onTest(connector.connector_id)}
        >
          Test connection
        </button>
      </div>
    </div>
  )
}

export function ConnectionsPage() {
  const qc = useQueryClient()
  const [testResult, setTestResult] = useState<{ id: string; ok: boolean; msg: string } | null>(null)
  const [testingAll, setTestingAll] = useState(false)

  const { data: connectors = [], isLoading } = useQuery<ConnectorMeta[]>({
    queryKey: ['connectors'],
    queryFn: () => connectorsApi.list(),
  })

  const { data: healthReport, refetch: refetchHealth } = useQuery({
    queryKey: ['connectors-health'],
    queryFn: () => connectorsApi.health(),
    enabled: connectors.length > 0,
    refetchInterval: 30_000,
    retry: false,
  })

  const healthMap = Object.fromEntries(
    (healthReport?.connectors ?? []).map(h => [h.connector_id, h])
  )

  const testMutation = useMutation({
    mutationFn: (id: string) => connectorsApi.test(id, {}),
    onSuccess: (data, id) => {
      setTestResult({ id, ok: data.success, msg: data.error ?? (data.success ? 'Connected' : 'Failed') })
      qc.invalidateQueries({ queryKey: ['connectors'] })
    },
    onError: (_err, id) => {
      setTestResult({ id, ok: false, msg: 'Connection test failed' })
    },
  })

  async function testAll() {
    setTestingAll(true)
    await refetchHealth()
    setTestingAll(false)
  }

  const grouped = connectors.reduce<Record<string, ConnectorMeta[]>>((acc, c) => {
    const g = c.family ?? 'Other'
    ;(acc[g] ??= []).push(c)
    return acc
  }, {})

  const available = healthReport?.available ?? 0
  const total = healthReport?.total ?? 0

  return (
    <div className="connections-page">
      <div className="connections-page__header">
        <h1 className="connections-page__title">Connections</h1>
        <div className="connections-page__header-right">
          {healthReport && (
            <span className={`health-summary ${available === total ? 'health-summary--ok' : 'health-summary--warn'}`}>
              {available}/{total} healthy
            </span>
          )}
          <button
            className="btn btn--ghost"
            onClick={testAll}
            disabled={testingAll || connectors.length === 0}
          >
            {testingAll ? 'Testing…' : 'Test all'}
          </button>
        </div>
      </div>

      {testResult && (
        <div className={`connections-page__toast ${testResult.ok ? 'connections-page__toast--ok' : 'connections-page__toast--fail'}`}>
          {testResult.id}: {testResult.msg}
          <button className="connections-page__toast-close" onClick={() => setTestResult(null)}>✕</button>
        </div>
      )}

      {isLoading ? (
        <div className="connections-page__empty">Loading…</div>
      ) : connectors.length === 0 ? (
        <div className="connections-page__empty">
          No connectors registered. Add connector configs to the backend registry.
        </div>
      ) : (
        Object.entries(grouped).map(([type, items]) => (
          <div key={type} className="connections-group">
            <div className="connections-group__label">{type}</div>
            <div className="connections-group__grid">
              {items.map((c) => (
                <ConnectorCard
                  key={c.connector_id}
                  connector={c}
                  health={healthMap[c.connector_id]}
                  onTest={(id) => testMutation.mutate(id)}
                />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
