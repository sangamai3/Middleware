import { useCanvasStore } from '@/store/canvasStore'
import type { CanvasNodeData } from '@/types'
import { ConnectorNodeConfig } from './ConnectorNodeConfig'
import './ConfigPanel.css'
import './ConnectorNodeConfig.css'

const FORMAT_EXTS = ['.csv', '.json', '.parquet', '.xlsx'] as const
const FORMAT_COLORS: Record<string, string> = {
  '.csv':     '#10B981',
  '.json':    '#F59E0B',
  '.parquet': '#8B5CF6',
  '.xlsx':    '#3B82F6',
}

function FormatConvertConfig({
  data,
  onUpdate,
}: {
  data: CanvasNodeData
  onUpdate: (patch: Partial<CanvasNodeData>) => void
}) {
  const cfg = (data.config as Record<string, unknown>) ?? {}
  const setData = (key: string, value: unknown) =>
    onUpdate({ config: { ...cfg, [key]: value } })

  const inFmt  = ((cfg.input_format  as string) || '').replace(/^\./, '')
  const outFmt = ((cfg.output_format as string) || '').replace(/^\./, '')

  return (
    <div className="ccn" style={{ marginTop: 8 }}>
      <div className="ccn-section-title">Input Format</div>
      <div className="ccn-fmt-row">
        {FORMAT_EXTS.map((ext) => {
          const label = ext.slice(1).toUpperCase()
          const active = inFmt === ext.slice(1)
          return (
            <button
              key={ext}
              type="button"
              className={`ccn-fmt-btn${active ? ' ccn-fmt-btn--active' : ''}`}
              style={active ? { background: `${FORMAT_COLORS[ext]}22`, borderColor: FORMAT_COLORS[ext], color: FORMAT_COLORS[ext] } : {}}
              onClick={() => setData('input_format', ext.slice(1))}
            >
              {label}
            </button>
          )
        })}
      </div>

      <div className="ccn-section-title" style={{ marginTop: 10 }}>Output Format</div>
      <div className="ccn-fmt-row">
        {FORMAT_EXTS.map((ext) => {
          const label = ext.slice(1).toUpperCase()
          const active = outFmt === ext.slice(1)
          return (
            <button
              key={ext}
              type="button"
              className={`ccn-fmt-btn${active ? ' ccn-fmt-btn--active' : ''}`}
              style={active ? { background: `${FORMAT_COLORS[ext]}22`, borderColor: FORMAT_COLORS[ext], color: FORMAT_COLORS[ext] } : {}}
              onClick={() => setData('output_format', ext.slice(1))}
            >
              {label}
            </button>
          )
        })}
      </div>

      {outFmt === 'json' && (
        <div className="config-field" style={{ marginTop: 10 }}>
          <label className="config-label">JSON orient</label>
          <select
            value={(cfg.json_orient as string) || 'records'}
            onChange={(e) => setData('json_orient', e.target.value)}
          >
            <option value="records">records (array of objects)</option>
            <option value="split">split (columns + data)</option>
            <option value="values">values (array of arrays)</option>
            <option value="index">index (keyed by row index)</option>
          </select>
        </div>
      )}

      {outFmt === 'parquet' && (
        <div className="config-field" style={{ marginTop: 10 }}>
          <label className="config-label">Parquet compression</label>
          <select
            value={(cfg.parquet_compression as string) || 'snappy'}
            onChange={(e) => setData('parquet_compression', e.target.value)}
          >
            <option value="snappy">snappy</option>
            <option value="gzip">gzip</option>
            <option value="brotli">brotli</option>
            <option value="none">none</option>
          </select>
        </div>
      )}

      {inFmt && outFmt && inFmt !== outFmt && (
        <div style={{ marginTop: 10, padding: '6px 10px', borderRadius: 6, background: 'var(--surface-2)', border: '1px solid var(--border)', fontSize: 11, color: 'var(--text-muted)' }}>
          DataFrame passes through unchanged — the Target connector writes as <strong style={{ color: 'var(--text)' }}>.{outFmt}</strong>
        </div>
      )}
      {inFmt && outFmt && inFmt === outFmt && (
        <div style={{ marginTop: 10, padding: '6px 10px', borderRadius: 6, background: 'var(--surface-2)', border: '1px solid var(--warn)', fontSize: 11, color: 'var(--warn)' }}>
          Input and output format are the same — no conversion will occur
        </div>
      )}
    </div>
  )
}

// Auto-generated config form based on step type
function StepConfigForm({
  data,
  onUpdate,
}: {
  data: CanvasNodeData
  onUpdate: (patch: Partial<CanvasNodeData>) => void
}) {
  const updateConfig = (key: string, value: string) => {
    onUpdate({ config: { ...data.config, [key]: value } })
  }
  const updateLabel = (label: string) => onUpdate({ label })

  return (
    <div className="config-form">
      <div className="config-field">
        <label className="config-label">Step name</label>
        <input
          value={data.label}
          onChange={(e) => updateLabel(e.target.value)}
          placeholder="Step name"
        />
      </div>

      {data.stepType === 'connector_read' && (
        <ConnectorNodeConfig data={data} onUpdate={onUpdate} mode="source" />
      )}

      {data.stepType === 'connector_write' && (
        <ConnectorNodeConfig data={data} onUpdate={onUpdate} mode="target" />
      )}

      {data.stepType === 'transform_format' && (
        <FormatConvertConfig data={data} onUpdate={onUpdate} />
      )}

      {data.stepType === 'transform_filter' && (
        <div className="config-field">
          <label className="config-label">Filter expression</label>
          <input
            value={(data.config.expression as string) || ''}
            onChange={(e) => updateConfig('expression', e.target.value)}
            placeholder='status == "active"'
          />
        </div>
      )}

      {data.stepType === 'set_variable' && (
        <div className="config-field">
          <label className="config-label">Variable name</label>
          <input
            value={(data.config.variable_name as string) || ''}
            onChange={(e) => updateConfig('variable_name', e.target.value)}
            placeholder="my_var"
          />
        </div>
      )}

      {data.stepType === 'logger' && (
        <>
          <div className="config-field">
            <label className="config-label">Message template</label>
            <input
              value={(data.config.message as string) || ''}
              onChange={(e) => updateConfig('message', e.target.value)}
              placeholder="Processed {rows} rows"
            />
          </div>
          <div className="config-field">
            <label className="config-label">Level</label>
            <select
              value={(data.config.level as string) || 'info'}
              onChange={(e) => updateConfig('level', e.target.value)}
            >
              <option value="debug">debug</option>
              <option value="info">info</option>
              <option value="warning">warning</option>
              <option value="error">error</option>
            </select>
          </div>
        </>
      )}

      {data.stepType === 'scheduler' && (
        <div className="config-field">
          <label className="config-label">Cron expression</label>
          <input
            value={(data.config.cron as string) || ''}
            onChange={(e) => updateConfig('cron', e.target.value)}
            placeholder="0 9 * * 1-5"
          />
        </div>
      )}

      {data.stepType === 'webhook_trigger' && (
        <div className="config-field">
          <label className="config-label">Path</label>
          <input
            value={(data.config.path as string) || ''}
            onChange={(e) => updateConfig('path', e.target.value)}
            placeholder="/webhook/my-flow"
          />
        </div>
      )}
    </div>
  )
}

export function ConfigPanel() {
  const { nodes, selectedNodeId, updateNodeData, deleteNode } = useCanvasStore()
  const node = nodes.find((n) => n.id === selectedNodeId)

  if (!node) {
    return (
      <div className="config-panel config-panel--empty">
        <p>Select a node to configure it</p>
      </div>
    )
  }

  return (
    <div className="config-panel">
      <div className="config-panel__header">
        <div>
          <div className="config-panel__title">{node.data.label}</div>
          <div className="config-panel__subtitle">
          {node.data.stepType === 'connector_read' ? 'Source Connector'
            : node.data.stepType === 'connector_write' ? 'Target Connector'
            : (node.data.stepType as string).replace(/_/g, ' ')}
        </div>
        </div>
        <button
          className="config-panel__delete"
          onClick={() => deleteNode(node.id)}
          title="Delete step"
        >
          ✕
        </button>
      </div>

      <div className="config-panel__body">
        <StepConfigForm
          data={node.data}
          onUpdate={(patch) => updateNodeData(node.id, patch)}
        />

        {node.data.status === 'failed' && node.data.error && (
          <div className="config-panel__error">
            <div className="config-panel__error-title">Last run error</div>
            <pre className="config-panel__error-body">{node.data.error}</pre>
          </div>
        )}
      </div>
    </div>
  )
}
