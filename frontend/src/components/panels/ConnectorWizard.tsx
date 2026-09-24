import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { connectorsApi } from '@/api/connectors'
import type { CanvasNodeData, ConnectorMeta, ColumnSchema, ObjectSchema } from '@/types'
import { ConnectorBrandIcon } from '@/components/connectors/ConnectorBrandIcon'
import { WizardStepper, type WizardStep } from '@/components/wizard/WizardStepper'
import {
  deleteSavedConnection,
  listSavedConnections,
  upsertSavedConnection,
  type SavedConnection,
} from '@/lib/savedConnections'
import { normalizeConnectionConfig } from '@/lib/connectionConfig'
import {
  FILE_SOURCE_OBJECT_DEFAULT,
  FILE_TARGET_OBJECT_DEFAULT,
  fileObjectDefault,
  resolveFileObject,
} from '@/lib/fileConnectorDefaults'
import {
  DEFAULT_TIMESTAMP_FORMAT,
  TIMESTAMP_FORMAT_CUSTOM,
  TIMESTAMP_FORMAT_PRESETS,
  previewTimestampFormat,
  timestampSelectValue,
} from '@/lib/timestampFormats'
import './ConnectorNodeConfig.css'

type StepId = 'connector' | 'connection' | 'objects' | 'preview' | 'options'

const FORMAT_EXTS = ['.csv', '.json', '.parquet', '.xlsx'] as const

function configFlag(cfg: Record<string, unknown>, key: string): boolean {
  const v = cfg[key]
  return v === true || v === 'true'
}

interface Props {
  data: CanvasNodeData
  onUpdate: (patch: Partial<CanvasNodeData>) => void
  mode: 'source' | 'target'
}

function usesObjectBrowser(meta?: ConnectorMeta) {
  if (!meta) return false
  if (['cloud_storage', 'file', 'messaging', 'rest'].includes(meta.family)) return false
  return true
}

function stepsFor(meta: ConnectorMeta | undefined, mode: 'source' | 'target'): WizardStep[] {
  if (!meta) {
    return [{ id: 'connector', label: 'Connector' }]
  }
  const base: WizardStep[] = [
    { id: 'connector', label: 'Connector' },
    { id: 'connection', label: 'Connection' },
  ]
  if (meta.family === 'rest') {
    return [...base, { id: 'objects', label: 'Endpoint' }, { id: 'options', label: 'Options' }]
  }
  if (['cloud_storage', 'file'].includes(meta.family)) {
    return [...base, { id: 'objects', label: mode === 'source' ? 'Source' : 'Target' }, { id: 'options', label: 'Options' }]
  }
  if (meta.family === 'messaging') {
    return [...base, { id: 'objects', label: 'Topic' }, { id: 'options', label: 'Options' }]
  }
  if (mode === 'source') {
    return [...base, { id: 'objects', label: 'Objects' }, { id: 'preview', label: 'Preview' }, { id: 'options', label: 'Options' }]
  }
  return [...base, { id: 'objects', label: 'Object' }, { id: 'options', label: 'Options' }]
}

export function ConnectorWizard({ data, onUpdate, mode }: Props) {
  const operation = mode === 'source' ? 'read' : 'write'
  const cfg = data.config as Record<string, unknown>
  const connectorId = (cfg.connector_id as string) || ''
  const conn = (cfg.conn as Record<string, string | boolean>) || {}
  const connected = !!cfg._connected

  const [step, setStep] = useState<StepId>('connector')
  const [savedId, setSavedId] = useState('')
  const [saveName, setSaveName] = useState('')
  const [objectFilter, setObjectFilter] = useState('')
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [testing, setTesting] = useState(false)

  const { data: connectors = [], isLoading } = useQuery({
    queryKey: ['connectors-list'],
    queryFn: () => connectorsApi.list(),
  })

  const filtered = connectors.filter((c) => c.operations.includes(operation))
  const selected = connectors.find((c) => c.connector_id === connectorId)
  const wizardSteps = useMemo(() => stepsFor(selected, mode), [selected, mode])

  const savedForConnector = listSavedConnections(connectorId)

  const objectName =
    selected?.family === 'file'
      ? resolveFileObject(cfg, mode)
      : (cfg.object as string) || (cfg.topic as string) || (cfg.endpoint as string) || ''

  const bootstrapped = useRef<string | null>(null)

  useEffect(() => {
    if (!connectorId) {
      setStep('connector')
      bootstrapped.current = null
      return
    }
    if (bootstrapped.current !== connectorId) {
      bootstrapped.current = connectorId
      if (!connected) {
        setStep('connection')
      } else if (
        selected &&
        ['cloud_storage', 'file', 'rest', 'messaging'].includes(selected.family) &&
        !objectName
      ) {
        setStep('objects')
      } else {
        setStep('options')
      }
      return
    }
    if (!connected) {
      setStep((s) => (s === 'connector' ? s : 'connection'))
    }
  }, [connectorId, connected, objectName, selected])

  useEffect(() => {
    if (step !== 'objects' || selected?.family !== 'file') return
    if (String(cfg.object ?? '').trim()) return
    const def = fileObjectDefault(mode, configFlag(cfg, 'write_per_source'))
    if (def) patchConfig({ object: def })
  }, [step, connectorId, mode, selected?.family])

  const setConnector = (id: string) => {
    onUpdate({
      config: {
        connector_id: id,
        conn: {},
        _connected: false,
        object: id === 'file' ? (mode === 'source' ? FILE_SOURCE_OBJECT_DEFAULT : '') : '',
        query: '',
        endpoint: '',
        topic: '',
      },
    })
    bootstrapped.current = id
    setStep('connection')
    setSavedId('')
    setTestMsg(null)
  }

  const patchConfig = (patch: Record<string, unknown>) => onUpdate({ config: patch })

  const setConn = (key: string, val: string | boolean) =>
    patchConfig({ conn: { ...conn, [key]: val } })

  const setData = (key: string, val: unknown) => patchConfig({ [key]: val })

  const applySaved = (entry: SavedConnection) => {
    setSavedId(entry.id)
    patchConfig({ conn: { ...entry.config }, _connected: false })
    setSaveName(entry.name)
    setTestMsg(null)
  }

  const connectionPayload = () =>
    normalizeConnectionConfig(conn, selected?.connection_schema) as Record<string, string>

  const runTest = async (): Promise<boolean> => {
    if (!selected) return false
    setTesting(true)
    setTestMsg(null)
    try {
      const payload = connectionPayload()
      const res = await connectorsApi.test(selected.connector_id, payload)
      if (res.success) {
        setTestMsg({ ok: true, text: 'Connection verified' })
        patchConfig({ conn: payload as Record<string, string | boolean>, _connected: true })
        return true
      }
      setTestMsg({ ok: false, text: res.error || 'Connection failed' })
      patchConfig({ _connected: false })
      return false
    } catch (e: unknown) {
      const text = e instanceof Error ? e.message : 'Connection failed'
      setTestMsg({ ok: false, text })
      patchConfig({ _connected: false })
      return false
    } finally {
      setTesting(false)
    }
  }

  const connectionFieldsValid = () => {
    const schema = selected?.connection_schema
    const required = schema?.required ?? []
    const payload = connectionPayload()
    return required.every((key) => {
      const v = payload[key]
      return v !== undefined && v !== null && String(v).trim() !== ''
    })
  }

  const continueFromConnection = async () => {
    if (!connectionFieldsValid()) {
      setTestMsg({ ok: false, text: 'Fill all required connection fields' })
      return
    }
    if (!connected) {
      const ok = await runTest()
      if (!ok) return
    }
    goNext()
  }

  const { data: objects = [], isLoading: objectsLoading, refetch: refetchObjects } = useQuery({
    queryKey: ['connector-objects', connectorId, JSON.stringify(conn)],
    queryFn: () => connectorsApi.objects(connectorId, connectionPayload()),
    enabled: connected && !!connectorId && step === 'objects' && usesObjectBrowser(selected),
    retry: false,
  })

  const { data: columns = [], isLoading: columnsLoading } = useQuery({
    queryKey: ['connector-columns', connectorId, objectName, JSON.stringify(conn)],
    queryFn: () => connectorsApi.columns(connectorId, connectionPayload(), objectName),
    enabled: connected && !!objectName && step === 'preview' && mode === 'source',
    retry: false,
  })

  const { data: sample, isLoading: sampleLoading, error: sampleError, refetch: refetchSample } = useQuery({
    queryKey: ['connector-sample', connectorId, objectName, JSON.stringify(conn)],
    queryFn: () => connectorsApi.sample(connectorId, connectionPayload(), objectName, 25),
    enabled: connected && !!objectName && step === 'preview' && mode === 'source',
    retry: false,
  })

  const filteredObjects = objects.filter((o) =>
    o.name.toLowerCase().includes(objectFilter.toLowerCase()),
  )

  const applyFileObjectDefaults = () => {
    if (selected?.family !== 'file') return
    const trimmed = String(cfg.object ?? '').trim()
    if (trimmed) return
    const def = fileObjectDefault(mode, configFlag(cfg, 'write_per_source'))
    if (def) patchConfig({ object: def })
  }

  const goNext = () => {
    if (step === 'objects') applyFileObjectDefaults()
    const idx = wizardSteps.findIndex((s) => s.id === step)
    if (idx < wizardSteps.length - 1) setStep(wizardSteps[idx + 1].id as StepId)
  }

  const goBack = () => {
    const idx = wizardSteps.findIndex((s) => s.id === step)
    if (idx > 0) setStep(wizardSteps[idx - 1].id as StepId)
  }

  if (!connectorId || step === 'connector') {
    return (
      <div className="ccn ccn--wizard">
        <WizardStepper steps={wizardSteps} currentId="connector" />
        <p className="ccn-lead">
          Choose a {mode === 'source' ? 'source' : 'target'} system. File, S3, Salesforce, databases, and REST are supported.
        </p>
        {isLoading ? (
          <div className="ccn-loading">Loading connectors…</div>
        ) : (
          <div className="ccn-grid ccn-grid--tiles">
            {filtered.map((c) => (
              <button
                key={c.connector_id}
                type="button"
                className="ccn-tile"
                onClick={() => setConnector(c.connector_id)}
              >
                <ConnectorBrandIcon connectorId={c.connector_id} size="lg" />
                <span className="ccn-tile__label">{c.label}</span>
                <span className="ccn-tile__meta">{c.family}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  if (!selected) return null

  if (step === 'connection') {
    const schema = selected.connection_schema
    const props = (schema?.properties || {}) as Record<
      string,
      { type?: string; description?: string; secret?: boolean; enum?: string[]; default?: unknown }
    >
    const required: string[] = schema?.required || []

    return (
      <div className="ccn ccn--wizard">
        <WizardStepper
          steps={wizardSteps}
          currentId="connection"
          onGoTo={(id) => setStep(id as StepId)}
        />
        <div className="ccn-hero">
          <ConnectorBrandIcon connectorId={connectorId} />
          <div>
            <div className="ccn-hero__title">{selected.label}</div>
            <div className="ccn-hero__sub">{mode === 'source' ? 'Inbound' : 'Outbound'} connection</div>
          </div>
          <button type="button" className="link-btn" onClick={() => setStep('connector')}>
            Change
          </button>
        </div>

        <div className="wiz-card">
          <div className="wiz-card__title">Saved connections</div>
          <select
            value={savedId}
            onChange={(e) => {
              const id = e.target.value
              setSavedId(id)
              if (!id) return
              const entry = savedForConnector.find((s) => s.id === id)
              if (entry) applySaved(entry)
            }}
          >
            <option value="">— Enter new connection details —</option>
            {savedForConnector.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          {savedForConnector.length > 0 && savedId && (
            <button
              type="button"
              className="link-btn ccn-save-del"
              onClick={() => {
                deleteSavedConnection(savedId)
                setSavedId('')
              }}
            >
              Remove saved
            </button>
          )}
        </div>

        <div className="ccn-section-title">Connection parameters</div>
        {Object.entries(props).map(([key, prop]) => (
          <div key={key} className={`config-field${prop.type === 'boolean' ? ' ccn-checkbox-row' : ''}`}>
            {prop.type === 'boolean' ? (
              <label className="ccn-checkbox-label">
                <input
                  type="checkbox"
                  checked={
                    conn[key] === true ||
                    conn[key] === 'true' ||
                    (conn[key] === undefined && prop.default === true)
                  }
                  onChange={(e) => setConn(key, e.target.checked)}
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
                    value={String(conn[key] ?? prop.default ?? '')}
                    onChange={(e) => setConn(key, e.target.value)}
                  >
                    {prop.enum.map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                ) : (
                  <input
                    type={prop.secret ? 'password' : prop.type === 'integer' ? 'number' : 'text'}
                    value={String(conn[key] ?? '')}
                    placeholder={prop.description || key.replace(/_/g, ' ')}
                    onChange={(e) => setConn(key, e.target.value)}
                    autoComplete={prop.secret ? 'new-password' : undefined}
                  />
                )}
              </>
            )}
          </div>
        ))}

        <div className="config-field">
          <label className="config-label">Save as (optional)</label>
          <input
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="Production Salesforce"
          />
        </div>

        {testMsg && (
          <div className={`status-pill ${testMsg.ok ? 'status-pill--ok' : 'status-pill--err'}`}>
            {testMsg.text}
          </div>
        )}

        <div className="wiz-footer">
          <button type="button" className="btn btn--ghost" onClick={goBack}>Back</button>
          <button
            type="button"
            className="btn btn--ghost"
            disabled={testing}
            onClick={() => {
              if (saveName.trim()) {
                const entry = upsertSavedConnection(connectorId, saveName, conn, savedId || undefined)
                setSavedId(entry.id)
              }
              void runTest()
            }}
          >
            {testing ? 'Testing…' : 'Test only'}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={testing || !connectionFieldsValid()}
            onClick={() => void continueFromConnection()}
          >
            {testing ? 'Testing…' : 'Test & continue'}
          </button>
        </div>
      </div>
    )
  }

  if (step === 'objects') {
    return (
      <ObjectStep
        mode={mode}
        selected={selected}
        conn={conn}
        cfg={cfg}
        objectFilter={objectFilter}
        setObjectFilter={setObjectFilter}
        objects={filteredObjects}
        objectsLoading={objectsLoading}
        onRefresh={() => refetchObjects()}
        setData={setData}
        wizardSteps={wizardSteps}
        onBack={goBack}
        onNext={goNext}
        onStep={(id) => setStep(id as StepId)}
        usesBrowser={usesObjectBrowser(selected)}
      />
    )
  }

  if (step === 'preview' && mode === 'source') {
    return (
      <div className="ccn ccn--wizard">
        <WizardStepper steps={wizardSteps} currentId="preview" onGoTo={(id) => setStep(id as StepId)} />
        <div className="ccn-section-title">Preview — {objectName}</div>
        <p className="ccn-lead">Live sample rows from the connector (up to 25).</p>
        {sampleLoading ? (
          <div className="ccn-loading">Loading data…</div>
        ) : sampleError ? (
          <div className="ccn-error">
            Could not load preview.{' '}
            <button type="button" className="link-btn" onClick={() => refetchSample()}>Retry</button>
          </div>
        ) : sample && sample.rows.length > 0 ? (
          <LiveSampleTable sample={sample} />
        ) : columnsLoading ? (
          <div className="ccn-loading">Loading schema…</div>
        ) : (
          <PreviewTable columns={columns} />
        )}
        <div className="wiz-footer">
          <button type="button" className="btn btn--ghost" onClick={goBack}>Back</button>
          <button type="button" className="btn btn--primary" onClick={goNext}>Continue</button>
        </div>
      </div>
    )
  }

  return (
    <OptionsStep
      mode={mode}
      selected={selected}
      cfg={cfg}
      setData={setData}
      wizardSteps={wizardSteps}
      onBack={goBack}
      onStep={(id) => setStep(id as StepId)}
      onChangeConnector={() => setStep('connector')}
      onChangeConnection={() => {
        patchConfig({ _connected: false })
        setStep('connection')
      }}
    />
  )
}

function ObjectStep({
  mode,
  selected,
  conn,
  cfg,
  objectFilter,
  setObjectFilter,
  objects,
  objectsLoading,
  onRefresh,
  setData,
  wizardSteps,
  onBack,
  onNext,
  onStep,
  usesBrowser,
}: {
  mode: 'source' | 'target'
  selected: ConnectorMeta
  conn: Record<string, string | boolean>
  cfg: Record<string, unknown>
  objectFilter: string
  setObjectFilter: (v: string) => void
  objects: ObjectSchema[]
  objectsLoading: boolean
  onRefresh: () => void
  setData: (k: string, v: unknown) => void
  wizardSteps: WizardStep[]
  onBack: () => void
  onNext: () => void
  onStep: (id: string) => void
  usesBrowser: boolean
}) {
  const family = selected.family
  const isStorage = ['cloud_storage', 'file'].includes(family)
  const isRest = family === 'rest'
  const isMessaging = family === 'messaging'
  const value = (cfg.object as string) || (cfg.topic as string) || (cfg.endpoint as string) || ''
  const writePerSource = family === 'file' && mode === 'target' && configFlag(cfg, 'write_per_source')

  const fileDefault =
    family === 'file' ? fileObjectDefault(mode, writePerSource) : null
  const fileObjectValue = family === 'file' ? resolveFileObject(cfg, mode) : value

  const canContinue = isMessaging
    ? !!String(cfg.topic as string || '').trim()
    : isRest
      ? !!String(cfg.endpoint as string || '').trim()
      : family === 'file'
        ? writePerSource || !!fileObjectValue.trim()
        : !!String(value).trim()

  return (
    <div className="ccn ccn--wizard">
      <WizardStepper steps={wizardSteps} currentId="objects" onGoTo={onStep} />

      {isStorage && (
        <>
          <div className="ccn-section-title">
            {family === 'file' ? 'File / folder' : 'S3 object path'}
          </div>
          {conn.base_path && (
            <div className="ccn-path-summary">
              <span className="ccn-path-label">Folder</span>
              <span className="ccn-path-value">{String(conn.base_path)}</span>
            </div>
          )}

          {family === 'file' && mode === 'target' && (
            <div className="config-field ccn-checkbox-row">
              <label className="ccn-checkbox-label">
                <input
                  type="checkbox"
                  checked={writePerSource}
                  onChange={(e) => setData('write_per_source', e.target.checked)}
                />
                Write one file per source file
              </label>
              <div className="ccn-hint-sm">
                Keeps each upstream file name (e.g. from a File source with a glob). Connect the
                target after your source step.
              </div>
            </div>
          )}

          {!(family === 'file' && mode === 'target' && writePerSource) && (
            <div className="config-field">
              <label className="config-label">
                {family === 'file'
                  ? mode === 'source' ? 'File name or pattern' : 'Output file name'
                  : 'Object key or prefix'}
              </label>
              <input
                value={(cfg.object as string) || ''}
                placeholder={fileDefault ?? 'incoming/data.csv'}
                onChange={(e) => setData('object', e.target.value)}
              />
              {family === 'file' && mode === 'source' && (
                <div className="ccn-hint-sm">
                  Default pattern is <code>{FILE_SOURCE_OBJECT_DEFAULT}</code> if left blank. Use globs
                  like <code>*.csv</code> for all CSV files in the folder.
                </div>
              )}
              {family === 'file' && mode === 'target' && !writePerSource && (
                <div className="ccn-hint-sm">
                  Default output name is <code>{FILE_TARGET_OBJECT_DEFAULT}</code> if left blank.
                </div>
              )}
            </div>
          )}

          {family === 'file' && mode === 'target' && writePerSource && (
            <div className="config-field">
              <label className="config-label">Output format</label>
              <div className="ccn-fmt-row ccn-fmt-row--block">
                {FORMAT_EXTS.map((ext) => {
                  const cur = (cfg.output_format as string) || '.csv'
                  const normalized = cur.startsWith('.') ? cur : `.${cur}`
                  return (
                    <button
                      key={ext}
                      type="button"
                      className={`ccn-fmt-btn${normalized === ext ? ' ccn-fmt-btn--active' : ''}`}
                      onClick={() => setData('output_format', ext)}
                    >
                      {ext.slice(1).toUpperCase()}
                    </button>
                  )
                })}
              </div>
              <div className="ccn-hint-sm">
                Optional conversion when writing — defaults to the source file extension.
              </div>
            </div>
          )}
        </>
      )}

      {isMessaging && (
        <div className="config-field">
          <label className="config-label">Kafka topic</label>
          <input
            value={(cfg.topic as string) || ''}
            onChange={(e) => setData('topic', e.target.value)}
            placeholder="events.orders"
          />
        </div>
      )}

      {isRest && (
        <div className="config-field">
          <label className="config-label">Endpoint path</label>
          <input
            value={(cfg.endpoint as string) || ''}
            onChange={(e) => setData('endpoint', e.target.value)}
            placeholder="/api/v1/customers"
          />
        </div>
      )}

      {usesBrowser && (
        <>
          <div className="ccn-obj-toolbar">
            <input
              className="ccn-search"
              value={objectFilter}
              onChange={(e) => setObjectFilter(e.target.value)}
              placeholder="Search objects…"
            />
            <button type="button" className="btn btn--ghost" onClick={onRefresh}>Refresh</button>
          </div>
          <div className="ccn-obj-catalog">
            {objectsLoading && <div className="ccn-loading">Loading catalog…</div>}
            {!objectsLoading && objects.length === 0 && (
              <div className="ccn-empty">No objects — check connection or refresh</div>
            )}
            {objects.map((o) => (
              <button
                key={o.name}
                type="button"
                className={`ccn-obj-card${value === o.name ? ' ccn-obj-card--active' : ''}`}
                onClick={() => setData('object', o.name)}
              >
                <span className="ccn-obj-kind">{o.kind}</span>
                <span className="ccn-obj-card__name">{o.name}</span>
                {o.description && <span className="ccn-obj-card__desc">{o.description}</span>}
              </button>
            ))}
          </div>
        </>
      )}

      <div className="wiz-footer">
        <button type="button" className="btn btn--ghost" onClick={onBack}>Back</button>
        <button type="button" className="btn btn--primary" disabled={!canContinue} onClick={onNext}>
          Continue to options
        </button>
      </div>
    </div>
  )
}

function LiveSampleTable({
  sample,
}: {
  sample: {
    columns: { name: string; data_type: string }[]
    rows: Record<string, unknown>[]
    row_count: number
    truncated: boolean
  }
}) {
  const cols = sample.columns.slice(0, 8)
  return (
    <>
      <div className="ccn-hint-sm" style={{ marginBottom: 8 }}>
        {sample.row_count} row{sample.row_count === 1 ? '' : 's'}
        {sample.truncated ? ' (showing first rows)' : ''}
      </div>
      <div className="ccn-preview-wrap">
        <table className="ccn-preview-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c.name}>{c.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sample.rows.map((row, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c.name}>{row[c.name] == null ? '—' : String(row[c.name])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function PreviewTable({ columns }: { columns: ColumnSchema[] }) {
  if (!columns.length) {
    return <div className="ccn-empty">No columns returned for this object</div>
  }
  const previewCols = columns.slice(0, 8)
  return (
    <div className="ccn-preview-wrap">
      <table className="ccn-preview-table">
        <thead>
          <tr>
            {previewCols.map((c) => (
              <th key={c.name}>{c.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[0, 1, 2].map((row) => (
            <tr key={row}>
              {previewCols.map((c) => (
                <td key={c.name}>
                  <span className="ccn-preview-placeholder">{c.data_type}</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ccn-hint-sm">Sample values appear when the flow runs</div>
    </div>
  )
}

function OptionsStep({
  mode,
  selected,
  cfg,
  setData,
  wizardSteps,
  onBack,
  onStep,
  onChangeConnector,
  onChangeConnection,
}: {
  mode: 'source' | 'target'
  selected: ConnectorMeta
  cfg: Record<string, unknown>
  setData: (k: string, v: unknown) => void
  wizardSteps: WizardStep[]
  onBack: () => void
  onStep: (id: string) => void
  onChangeConnector: () => void
  onChangeConnection: () => void
}) {
  const family = selected.family
  const isSql = ['sql', 'analytics'].includes(family)
  const isSoql = family === 'saas' && selected.connector_id === 'salesforce'
  const isRest = family === 'rest'
  const isFileTarget = mode === 'target' && family === 'file'
  const addTimestamp = isFileTarget && configFlag(cfg, 'add_timestamp')
  const writePerSource = isFileTarget && configFlag(cfg, 'write_per_source')

  return (
    <div className="ccn ccn--wizard">
      <WizardStepper steps={wizardSteps} currentId="options" onGoTo={onStep} />
      <div className="ccn-summary-bar">
        <ConnectorBrandIcon connectorId={selected.connector_id} size="sm" />
        <span>{selected.label}</span>
        <span className="ccn-summary-bar__obj">{(cfg.object as string) || (cfg.endpoint as string) || '—'}</span>
      </div>
      <div className="ccn-quick-links">
        <button type="button" className="link-btn" onClick={onChangeConnector}>Change connector</button>
        <span>·</span>
        <button type="button" className="link-btn" onClick={onChangeConnection}>Edit connection</button>
      </div>

      <div className="ccn-section-title">Run options</div>

      {mode === 'source' && (isSql || isSoql) && (
        <div className="config-field">
          <label className="config-label">{isSoql ? 'SOQL' : 'SQL'} <span className="ccn-optional">(optional)</span></label>
          <textarea
            className="ccn-query"
            value={(cfg.query as string) || ''}
            rows={4}
            onChange={(e) => setData('query', e.target.value)}
            placeholder={isSoql ? 'SELECT Id, Name FROM Account LIMIT 100' : 'SELECT * FROM customers'}
          />
        </div>
      )}

      {isRest && mode === 'source' && (
        <div className="config-field">
          <label className="config-label">Response data path</label>
          <input
            value={(cfg.data_path as string) || ''}
            onChange={(e) => setData('data_path', e.target.value)}
            placeholder="data.items"
          />
        </div>
      )}

      {mode === 'source' && (
        <div className="config-field">
          <label className="config-label">Row limit</label>
          <input
            type="number"
            min={1}
            value={(cfg.limit as number) || ''}
            placeholder="Unlimited"
            onChange={(e) => setData('limit', e.target.value ? Number(e.target.value) : '')}
          />
        </div>
      )}

      {mode === 'target' && (
        <>
          {isFileTarget && (
            <div className="config-field ccn-checkbox-row">
              <label className="ccn-checkbox-label">
                <input
                  type="checkbox"
                  checked={addTimestamp}
                  onChange={(e) => setData('add_timestamp', e.target.checked)}
                />
                Append timestamp to filename
              </label>
              {addTimestamp && (
                <>
                  <div className="config-field" style={{ marginTop: 10 }}>
                    <label className="config-label">Timestamp format</label>
                    <select
                      value={timestampSelectValue(String(cfg.timestamp_format ?? DEFAULT_TIMESTAMP_FORMAT))}
                      onChange={(e) => {
                        const v = e.target.value
                        setData(
                          'timestamp_format',
                          v === TIMESTAMP_FORMAT_CUSTOM ? '' : v,
                        )
                      }}
                    >
                      {TIMESTAMP_FORMAT_PRESETS.map((p) => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                      <option value={TIMESTAMP_FORMAT_CUSTOM}>Custom strftime pattern…</option>
                    </select>
                    {timestampSelectValue(String(cfg.timestamp_format ?? '')) === TIMESTAMP_FORMAT_CUSTOM && (
                      <input
                        style={{ marginTop: 8 }}
                        value={(cfg.timestamp_format as string) || ''}
                        placeholder="%Y%m%d_%H%M%S"
                        onChange={(e) => setData('timestamp_format', e.target.value)}
                      />
                    )}
                    <div className="ccn-hint-sm">
                      Preview:{' '}
                      <code>
                        {previewTimestampFormat(
                          String(cfg.timestamp_format || DEFAULT_TIMESTAMP_FORMAT),
                        )}
                      </code>
                      {' '}(Python strftime)
                    </div>
                  </div>
                  <div className="ccn-hint-sm">
                    {writePerSource
                      ? (() => {
                          const ts = previewTimestampFormat(
                            (cfg.timestamp_format as string) || DEFAULT_TIMESTAMP_FORMAT,
                          )
                          const ext = (cfg.output_format as string) || '.csv'
                          return `e.g. customers_${ts}${ext}`
                        })()
                      : (() => {
                          const obj = (cfg.object as string) || 'output.csv'
                          const ts = previewTimestampFormat(
                            (cfg.timestamp_format as string) || DEFAULT_TIMESTAMP_FORMAT,
                          )
                          const dot = obj.lastIndexOf('.')
                          return dot > 0
                            ? `e.g. ${obj.slice(0, dot)}_${ts}${obj.slice(dot)}`
                            : `e.g. ${obj}_${ts}`
                        })()}
                  </div>
                </>
              )}
            </div>
          )}

          <div className="config-field">
            <label className="config-label">Write mode</label>
            <select value={(cfg.mode as string) || 'replace'} onChange={(e) => setData('mode', e.target.value)}>
              <option value="replace">Replace</option>
              <option value="append">Append</option>
              <option value="upsert">Upsert</option>
            </select>
          </div>
          {(cfg.mode as string) === 'upsert' && (
            <div className="config-field">
              <label className="config-label">Upsert key</label>
              <input
                value={(cfg.upsert_key as string) || ''}
                onChange={(e) => setData('upsert_key', e.target.value)}
              />
            </div>
          )}
        </>
      )}

      <div className="wiz-footer">
        <button type="button" className="btn btn--ghost" onClick={onBack}>Back</button>
        <span className="status-pill status-pill--ok">Ready to save flow</span>
      </div>
    </div>
  )
}
