import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { connectorsApi, type ConnectorHealthEntry } from '@/api/connectors'
import { ConnectorBrandIcon } from '@/components/connectors/ConnectorBrandIcon'
import type { ConnectorMeta } from '@/types'
import {
  EmptyPanel,
  KpiGrid,
  PageHeader,
  SurfaceCard,
} from '@/components/ui/enterprise/PageChrome'
import '@/components/ui/enterprise/PageChrome.css'
import './ConnectionsPage.css'

function HealthDot({ status }: { status?: ConnectorHealthEntry['status'] }) {
  const tone =
    status === 'available' ? 'conn-health--ok' : status ? 'conn-health--bad' : 'conn-health--unknown'
  const label = status === 'available' ? 'Healthy' : status ?? 'Unknown'
  return (
    <span className={`conn-health ${tone}`}>
      <span className="conn-health__dot" />
      {label}
    </span>
  )
}

function ConnectorCard({
  connector,
  health,
  onTest,
  testing,
}: {
  connector: ConnectorMeta
  health?: ConnectorHealthEntry
  onTest: (id: string) => void
  testing: boolean
}) {
  return (
    <article className="conn-catalog-card">
      <div className="conn-catalog-card__top">
        <ConnectorBrandIcon connectorId={connector.connector_id} size="lg" />
        <div className="conn-catalog-card__head">
          <h3 className="conn-catalog-card__name">{connector.label}</h3>
          <span className="badge badge--muted">{connector.family}</span>
        </div>
        <HealthDot status={health?.status} />
      </div>
      <p className="conn-catalog-card__id">{connector.connector_id}</p>
      {connector.description && (
        <p className="conn-catalog-card__desc">{connector.description}</p>
      )}
      {health?.message && health.status !== 'available' && (
        <p className="conn-catalog-card__err">{health.message}</p>
      )}
      <div className="conn-catalog-card__ops">
        {connector.operations.slice(0, 4).map((op) => (
          <span key={op} className="conn-catalog-card__op">{op}</span>
        ))}
        {connector.operations.length > 4 && (
          <span className="conn-catalog-card__op">+{connector.operations.length - 4}</span>
        )}
      </div>
      <button
        type="button"
        className="btn btn--secondary conn-catalog-card__test"
        disabled={testing}
        onClick={() => onTest(connector.connector_id)}
      >
        {testing ? 'Testing…' : 'Test connection'}
      </button>
    </article>
  )
}

export function ConnectionsPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [familyFilter, setFamilyFilter] = useState<string>('all')
  const [testResult, setTestResult] = useState<{ id: string; ok: boolean; msg: string } | null>(null)
  const [testingAll, setTestingAll] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)

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
    (healthReport?.connectors ?? []).map((h) => [h.connector_id, h]),
  )

  const families = useMemo(() => {
    const set = new Set(connectors.map((c) => c.family ?? 'Other'))
    return ['all', ...Array.from(set).sort()]
  }, [connectors])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return connectors.filter((c) => {
      if (familyFilter !== 'all' && (c.family ?? 'Other') !== familyFilter) return false
      if (!q) return true
      return (
        c.label.toLowerCase().includes(q)
        || c.connector_id.toLowerCase().includes(q)
        || (c.description?.toLowerCase().includes(q) ?? false)
      )
    })
  }, [connectors, search, familyFilter])

  const grouped = useMemo(() => {
    return filtered.reduce<Record<string, ConnectorMeta[]>>((acc, c) => {
      const g = c.family ?? 'Other'
      ;(acc[g] ??= []).push(c)
      return acc
    }, {})
  }, [filtered])

  const testMutation = useMutation({
    mutationFn: (id: string) => {
      setTestingId(id)
      return connectorsApi.test(id, {})
    },
    onSettled: () => setTestingId(null),
    onSuccess: (data, id) => {
      setTestResult({
        id,
        ok: data.success,
        msg: data.error ?? (data.success ? 'Connection successful' : 'Test failed'),
      })
      qc.invalidateQueries({ queryKey: ['connectors'] })
      refetchHealth()
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

  const available = healthReport?.available ?? 0
  const total = healthReport?.total ?? connectors.length
  const unhealthy = Math.max(0, total - available)

  return (
    <div className="page-shell ep-page connections-page">
      <PageHeader
        meta="Platform connectors"
        title="Connections"
        description="Registered connector types and runtime health. Flow-specific credentials are configured in the flow designer when you add a source or target step."
        actions={
          <>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={testAll}
              disabled={testingAll || connectors.length === 0}
            >
              {testingAll ? 'Refreshing…' : 'Refresh health'}
            </button>
          </>
        }
      />

      <KpiGrid
        items={[
          { id: 'total', label: 'Connectors', value: connectors.length, hint: 'Available in runtime' },
          {
            id: 'healthy',
            label: 'Healthy',
            value: healthReport ? available : '—',
            tone: 'success',
            hint: healthReport ? `of ${total} reporting` : 'Run health check',
          },
          {
            id: 'issues',
            label: 'Degraded',
            value: healthReport ? unhealthy : '—',
            tone: unhealthy > 0 ? 'warn' : 'default',
            hint: 'Unavailable or error',
          },
        ]}
      />

      {testResult && (
        <div
          className={`connections-toast ${testResult.ok ? 'connections-toast--ok' : 'connections-toast--fail'}`}
          role="status"
        >
          <strong>{testResult.id}</strong> — {testResult.msg}
          <button type="button" className="connections-toast__close" onClick={() => setTestResult(null)}>
            ×
          </button>
        </div>
      )}

      <SurfaceCard noPadding>
        <div className="connections-page__toolbar-wrap">
          <div className="ep-toolbar">
            <div className="ep-search">
              <span className="ep-search__icon" aria-hidden>⌕</span>
              <input
                type="search"
                placeholder="Search connectors…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Search connectors"
              />
            </div>
            <div className="ep-chips">
              {families.map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`ep-chip${familyFilter === f ? ' ep-chip--on' : ''}`}
                  onClick={() => setFamilyFilter(f)}
                >
                  {f === 'all' ? 'All families' : f}
                </button>
              ))}
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="connections-page__loading">Loading connectors…</div>
        ) : connectors.length === 0 ? (
          <EmptyPanel
            icon="⎔"
            title="No connectors"
            description="Register connector plugins on the API to see them here."
          />
        ) : filtered.length === 0 ? (
          <EmptyPanel
            title="No matches"
            description="Adjust search or family filter."
            action={
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => { setSearch(''); setFamilyFilter('all') }}
              >
                Clear filters
              </button>
            }
          />
        ) : (
          <div className="connections-catalog">
            {Object.entries(grouped).map(([family, items]) => (
              <section key={family} className="connections-catalog__section">
                <h2 className="connections-catalog__family">{family}</h2>
                <div className="connections-catalog__grid">
                  {items.map((c) => (
                    <ConnectorCard
                      key={c.connector_id}
                      connector={c}
                      health={healthMap[c.connector_id]}
                      onTest={(id) => testMutation.mutate(id)}
                      testing={testingId === c.connector_id}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </SurfaceCard>
    </div>
  )
}
