import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { connectorsApi } from '@/api/connectors'
import type { CanvasNodeData } from '@/types'
import './ConnectorNodeConfig.css'

const ICONS: Record<string, string> = {
  postgres:     'PG',
  salesforce:   'SF',
  'aws-s3':     'S3',
  'rest-api':   'API',
  file:         'FILE',
  redis:        'RD',
  bigquery:     'BQ',
  snowflake:    'SF❄',
  mongodb:      'MDB',
  kafka:        'KFK',
  slack:        'SLK',
  anthropic:    'AI',
  openai:       'GPT',
  http_sidecar: 'HTTP',
}

const FAMILY_COLOR: Record<string, string> = {
  sql:           '#4A90D9',
  analytics:     '#7B5EA7',
  saas:          '#00A1E0',
  cloud_storage: '#FF9900',
  file:          '#6B7280',
  nosql:         '#4CAF50',
  messaging:     '#E91E63',
  rest:          '#16A34A',
  communication: '#4A154B',
  ai:            '#8B5CF6',
  polyglot:      '#64748B',
}

type Phase = 'pick' | 'connect' | 'data'

interface Props {
  data: CanvasNodeData
  onUpdate: (patch: Partial<CanvasNodeData>) => void
  mode: 'source' | 'target'
}

export function ConnectorNodeConfig({ data, onUpdate, mode }: Props) {
  const operation = mode === 'source' ? 'read' : 'write'
  const cfg = data.config as Record<string, unknown>
  const connectorId = (cfg.connector_id as string) || ''
  const conn = (cfg.conn as Record<string, string>) || {}
  const connected = !!(cfg._connected)

  const phase: Phase = !connectorId ? 'pick' : !connected ? 'connect' : 'data'

  const { data: connectors = [], isLoading } = useQuery({
    queryKey: ['connectors-list'],
    queryFn: () => connectorsApi.list(),
  })

  const filtered = connectors.filter((c) => c.operations.includes(operation))
  const selected = connectors.find((c) => c.connector_id === connectorId)

  const setConnector = (id: string) =>
    onUpdate({ config: { connector_id: id, conn: {}, _connected: false } })

  const resetToPickStep = () =>
    onUpdate({ config: { connector_id: '', conn: {}, _connected: false } })

  const resetToConnectStep = () =>
    onUpdate({ config: { ...cfg, _connected: false } })

  const setConn = (key: string, val: string) =>
    onUpdate({ config: { ...cfg, conn: { ...conn, [key]: val } } })

  const setData = (key: string, val: unknown) =>
    onUpdate({ config: { ...cfg, [key]: val } })

  const markConnected = () =>
    onUpdate({ config: { ...cfg, _connected: true } })

  /* ── STEP 1: pick connector ─────────────────────────────────────── */
  if (phase === 'pick') {
    return (
      <div className="ccn">
        <div className="ccn-hint">Choose a {mode} connector</div>
        {isLoading ? (
          <div className="ccn-loading">Loading connectors…</div>
        ) : (
          <div className="ccn-grid">
            {filtered.map((c) => (
              <button
                key={c.connector_id}
                className="ccn-card"
                style={{ '--ccn-color': FAMILY_COLOR[c.family] || '#6B7280' } as React.CSSProperties}
                onClick={() => setConnector(c.connector_id)}
              >
                <span className="ccn-card__icon">{ICONS[c.connector_id] || c.connector_id.slice(0, 3).toUpperCase()}</span>
                <span className="ccn-card__label">{c.label}</span>
                <span className="ccn-card__family">{c.family}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  /* ── STEP 2: connection credentials ─────────────────────────────── */
  if (phase === 'connect' && selected) {
    const schema = selected.connection_schema
    const props = (schema?.properties || {}) as Record<string, { type?: string; description?: string; secret?: boolean; enum?: string[]; default?: unknown }>
    const required: string[] = schema?.required || []
    const missingRequired = required.some((k) => !conn[k])

    return (
      <div className="ccn">
        <div className="ccn-breadcrumb">
          <button className="ccn-back" onClick={resetToPickStep}>← All connectors</button>
          <span
            className="ccn-badge"
            style={{ background: FAMILY_COLOR[selected.family] || '#6B7280' }}
          >
            {selected.label}
          </span>
        </div>
        <div className="ccn-section-title">Connection settings</div>

        {Object.entries(props).map(([key, prop]) => (
          <div key={key} className={`config-field${prop.type === 'boolean' ? ' ccn-checkbox-row' : ''}`}>
            {prop.type === 'boolean' ? (
              <label className="ccn-checkbox-label">
                <input
                  type="checkbox"
                  checked={conn[key] === 'true' || (conn[key] === undefined && prop.default === true)}
                  onChange={(e) => setConn(key, String(e.target.checked))}
                />
                {key.replace(/_/g, ' ')}
              </label>
            ) : (
              <>
                <label className="config-label">
                  {key.replace(/_/g, ' ')}
                  {required.includes(key) && <span className="ccn-req"> *</span>}
                </label>
                {prop.enum ? (
                  <select
                    value={conn[key] || String(prop.default ?? '')}
                    onChange={(e) => setConn(key, e.target.value)}
                  >
                    {prop.enum.map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                ) : (
                  <input
                    type={prop.secret ? 'password' : prop.type === 'integer' ? 'number' : 'text'}
                    value={conn[key] || ''}
                    placeholder={prop.description || key.replace(/_/g, ' ')}
                    onChange={(e) => setConn(key, e.target.value)}
                    autoComplete={prop.secret ? 'new-password' : undefined}
                  />
                )}
              </>
            )}
          </div>
        ))}

        <button
          className="ccn-continue"
          disabled={missingRequired}
          onClick={markConnected}
          title={missingRequired ? 'Fill required fields first' : undefined}
        >
          Continue →
        </button>
      </div>
    )
  }

  /* ── STEP 3: data config ─────────────────────────────────────────── */
  if (phase === 'data' && selected) {
    const family = selected.family
    const isSql = ['sql', 'analytics'].includes(family)
    const isSoql = family === 'saas' && selected.connector_id === 'salesforce'
    const isStorage = ['cloud_storage', 'file'].includes(family)
    const isMessaging = family === 'messaging'
    const isRest = family === 'rest'

    return (
      <div className="ccn">
        <div className="ccn-breadcrumb">
          <button className="ccn-back" onClick={resetToConnectStep}>← Connection</button>
          <span
            className="ccn-badge"
            style={{ background: FAMILY_COLOR[selected.family] || '#6B7280' }}
          >
            {selected.label}
          </span>
        </div>
        <div className="ccn-section-title">{mode === 'source' ? 'Source' : 'Target'} data</div>

        {/* Object / Table picker */}
        {!isStorage && !isMessaging && !isRest && (
          <div className="config-field">
            <label className="config-label">
              {isSoql ? 'Object' : isMessaging ? 'Topic' : 'Table / Collection'}
            </label>
            <ObjectPicker
              connectorId={selected.connector_id}
              conn={conn}
              value={(cfg.object as string) || ''}
              onChange={(v) => setData('object', v)}
            />
          </div>
        )}

        {/* Storage: file/object name */}
        {isStorage && (
          <>
            {/* Show folder path from connection config (read-only summary) */}
            {conn.base_path && (
              <div className="ccn-path-summary">
                <span className="ccn-path-label">Folder</span>
                <span className="ccn-path-value" title={conn.base_path}>{conn.base_path}</span>
                <button className="ccn-path-edit" onClick={resetToConnectStep} title="Edit folder path">✎</button>
              </div>
            )}

            {/* Write-per-source toggle (target only, before filename input) */}
            {family === 'file' && mode === 'target' && (
              <div className="config-field ccn-checkbox-row">
                <label className="ccn-checkbox-label">
                  <input
                    type="checkbox"
                    checked={cfg.write_per_source === 'true' || cfg.write_per_source === true}
                    onChange={(e) => setData('write_per_source', String(e.target.checked))}
                  />
                  Write one file per source file
                </label>
                {(cfg.write_per_source === 'true' || cfg.write_per_source === true) && (
                  <div className="ccn-hint-sm">Each file keeps its original name in the target folder</div>
                )}
              </div>
            )}

            {/* Output file name — hidden when write_per_source is on */}
            {!(family === 'file' && mode === 'target' && (cfg.write_per_source === 'true' || cfg.write_per_source === true)) && (
              <div className="config-field">
                <label className="config-label">
                  {family === 'file'
                    ? mode === 'source' ? 'File name or pattern' : 'Output file name'
                    : mode === 'source' ? 'S3 path / prefix' : 'S3 output path'}
                </label>
                <input
                  value={(cfg.object as string) || ''}
                  placeholder={
                    family === 'file'
                      ? mode === 'source' ? '*.csv  or  customers.csv' : 'output.csv'
                      : mode === 'source' ? 's3://bucket/prefix/' : 's3://bucket/output/'
                  }
                  onChange={(e) => setData('object', e.target.value)}
                />
                {family === 'file' && mode === 'source' && (
                  <div className="ccn-hint-sm">Use <code>*.csv</code> to read all CSV files in the folder</div>
                )}
              </div>
            )}

            {/* Timestamp option for target */}
            {family === 'file' && mode === 'target' && (
              <div className="config-field ccn-checkbox-row">
                <label className="ccn-checkbox-label">
                  <input
                    type="checkbox"
                    checked={cfg.add_timestamp === 'true' || cfg.add_timestamp === true}
                    onChange={(e) => setData('add_timestamp', String(e.target.checked))}
                  />
                  Append timestamp to filename
                </label>
                {(cfg.add_timestamp === 'true' || cfg.add_timestamp === true) && (
                  <div className="ccn-hint-sm">
                    {(cfg.write_per_source === 'true' || cfg.write_per_source === true)
                      ? 'e.g. original_YYYYMMDD_HHMMSS.csv'
                      : (() => {
                          const obj = (cfg.object as string) || ''
                          if (!obj) return 'e.g. output_YYYYMMDD_HHMMSS.csv'
                          const dot = obj.lastIndexOf('.')
                          return `e.g. ${dot > 0 ? `${obj.slice(0, dot)}_YYYYMMDD_HHMMSS${obj.slice(dot)}` : `${obj}_YYYYMMDD_HHMMSS`}`
                        })()
                    }
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* Messaging: topic */}
        {isMessaging && (
          <div className="config-field">
            <label className="config-label">Topic</label>
            <input
              value={(cfg.topic as string) || ''}
              placeholder="my-topic"
              onChange={(e) => setData('topic', e.target.value)}
            />
          </div>
        )}

        {/* REST API: endpoint + method */}
        {isRest && (
          <>
            <div className="config-field">
              <label className="config-label">Endpoint path</label>
              <input
                value={(cfg.endpoint as string) || ''}
                placeholder="/api/v1/records"
                onChange={(e) => setData('endpoint', e.target.value)}
              />
            </div>
            <div className="config-field">
              <label className="config-label">Method</label>
              <select value={(cfg.method as string) || (mode === 'source' ? 'GET' : 'POST')} onChange={(e) => setData('method', e.target.value)}>
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
              </select>
            </div>
            {mode === 'source' && (
              <div className="config-field">
                <label className="config-label">Response data path (JSONPath)</label>
                <input
                  value={(cfg.data_path as string) || ''}
                  placeholder="$.data.records"
                  onChange={(e) => setData('data_path', e.target.value)}
                />
              </div>
            )}
          </>
        )}

        {/* SQL / SOQL query editor (source only) */}
        {mode === 'source' && (isSql || isSoql) && (
          <div className="config-field">
            <label className="config-label">
              {isSoql ? 'SOQL query' : 'SQL query'}
              <span className="ccn-optional"> (optional override)</span>
            </label>
            <textarea
              className="ccn-query"
              value={(cfg.query as string) || ''}
              placeholder={
                isSoql
                  ? 'SELECT Id, Name, Amount FROM Opportunity WHERE StageName = \'Closed Won\''
                  : 'SELECT * FROM customers\nWHERE created_at >= NOW() - INTERVAL \'7 days\''
              }
              rows={5}
              onChange={(e) => setData('query', e.target.value)}
            />
            <div className="ccn-hint-sm">Leave empty to read all rows from the selected table</div>
          </div>
        )}

        {/* Filter (nosql / generic) for source */}
        {mode === 'source' && family === 'nosql' && (
          <div className="config-field">
            <label className="config-label">Filter (JSON)</label>
            <textarea
              className="ccn-query"
              value={(cfg.filter as string) || ''}
              placeholder={'{"status": "active", "age": {"$gt": 18}}'}
              rows={3}
              onChange={(e) => setData('filter', e.target.value)}
            />
          </div>
        )}

        {/* Row limit (source) */}
        {mode === 'source' && (
          <div className="config-field">
            <label className="config-label">Row limit</label>
            <input
              type="number"
              value={(cfg.limit as number) || ''}
              placeholder="unlimited"
              min={1}
              onChange={(e) => setData('limit', e.target.value ? Number(e.target.value) : '')}
            />
          </div>
        )}

        {/* Write mode (target) */}
        {mode === 'target' && (
          <>
            <div className="config-field">
              <label className="config-label">Write mode</label>
              <select value={(cfg.mode as string) || 'replace'} onChange={(e) => setData('mode', e.target.value)}>
                <option value="replace">Replace — overwrite existing data</option>
                <option value="append">Append — add to existing rows</option>
                <option value="upsert">Upsert — merge on key</option>
              </select>
            </div>
            {(cfg.mode as string) === 'upsert' && (
              <div className="config-field">
                <label className="config-label">Upsert key column(s)</label>
                <input
                  value={(cfg.upsert_key as string) || ''}
                  placeholder="id, email"
                  onChange={(e) => setData('upsert_key', e.target.value)}
                />
              </div>
            )}
          </>
        )}
      </div>
    )
  }

  return null
}

/* ── Object picker with Browse button ───────────────────────────────── */
function ObjectPicker({ connectorId, conn, value, onChange }: {
  connectorId: string
  conn: Record<string, string>
  value: string
  onChange: (v: string) => void
}) {
  const [browsing, setBrowsing] = useState(false)

  const { data: objects = [], isLoading, isError } = useQuery({
    queryKey: ['connector-objects', connectorId, JSON.stringify(conn)],
    queryFn: () => connectorsApi.objects(connectorId, conn),
    enabled: browsing,
    retry: false,
  })

  return (
    <div className="ccn-obj">
      <div className="ccn-obj-row">
        <input
          value={value}
          placeholder="table_name"
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          className="ccn-browse"
          onClick={() => setBrowsing((b) => !b)}
          title="Browse available tables/objects"
        >
          {browsing ? '▲' : 'Browse'}
        </button>
      </div>

      {browsing && (
        <div className="ccn-obj-list">
          {isLoading && <div className="ccn-loading">Loading…</div>}
          {isError && <div className="ccn-error">Could not load — check connection</div>}
          {!isLoading && !isError && objects.length === 0 && (
            <div className="ccn-empty">No objects found</div>
          )}
          {objects.map((o) => (
            <button
              key={o.name}
              className={`ccn-obj-item ${value === o.name ? 'ccn-obj-item--active' : ''}`}
              onClick={() => { onChange(o.name); setBrowsing(false) }}
            >
              <span className="ccn-obj-kind">{o.kind}</span>
              {o.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
