import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import type { NodeProps, Node } from '@xyflow/react'
import type { CanvasNodeData, NodeFamily, StepStatus } from '@/types'
import clsx from 'clsx'
import './BaseNode.css'

const FAMILY_COLOR: Record<NodeFamily, string> = {
  trigger: 'var(--node-trigger)',
  connector: 'var(--node-connector)',
  transform: 'var(--node-transform)',
  control: 'var(--node-control)',
  utility: 'var(--node-utility)',
}

const STATUS_ICON: Record<StepStatus, string> = {
  pending: '',
  running: '⟳',
  success: '✓',
  failed: '✗',
  retrying: '↺',
  skipped: '○',
}

const STEP_ICONS: Record<string, string> = {
  scheduler: '⏰', webhook_trigger: '⚡', event_trigger: '⬆',
  connector_read: '⬇', connector_write: '⬆',
  transform_format: '⇄',
  transform_map: '⇌', transform_filter: '⧉', transform_sql: '◧', transform_script: '{ }',
  router: '⑂', merge: '⑃', iterator: '⟲', sub_flow: '▣',
  set_variable: 'x=', logger: '☰', approval: '✓?', notification: '🔔', sync_endpoint: '⇋',
  global_exception: '⚠', component_exception: '⚠',
}

// Short badge label per connector id
const CONNECTOR_ICONS: Record<string, string> = {
  postgres:     'PG',
  salesforce:   'SF',
  'aws-s3':     'S3',
  'rest-api':   'API',
  file:         'CSV',
  redis:        'RD',
  bigquery:     'BQ',
  snowflake:    'SFW',
  mongodb:      'MDB',
  kafka:        'KFK',
  slack:        'SLK',
  anthropic:    'AI',
  openai:       'GPT',
  http_sidecar: 'HTTP',
}

// Human-readable connector name
const CONNECTOR_LABELS: Record<string, string> = {
  postgres:     'PostgreSQL',
  salesforce:   'Salesforce',
  'aws-s3':     'AWS S3',
  'rest-api':   'REST API',
  file:         'CSV / File',
  redis:        'Redis',
  bigquery:     'BigQuery',
  snowflake:    'Snowflake',
  mongodb:      'MongoDB',
  kafka:        'Kafka',
  slack:        'Slack',
  anthropic:    'Anthropic AI',
  openai:       'OpenAI',
  http_sidecar: 'HTTP Sidecar',
}

// Accent color per connector id
const CONNECTOR_COLORS: Record<string, string> = {
  postgres:     '#4A90D9',
  salesforce:   '#00A1E0',
  'aws-s3':     '#FF9900',
  'rest-api':   '#16A34A',
  file:         '#10B981',
  redis:        '#DC2626',
  bigquery:     '#7B5EA7',
  snowflake:    '#56B9F2',
  mongodb:      '#4CAF50',
  kafka:        '#E91E63',
  slack:        '#4A154B',
  anthropic:    '#8B5CF6',
  openai:       '#10A37F',
  http_sidecar: '#64748B',
}

export type CanvasNode = Node<CanvasNodeData>

export const BaseNode = memo(({ data, selected }: NodeProps<CanvasNode>) => {
  const color = FAMILY_COLOR[data.family as NodeFamily]
  const statusIcon = data.status ? STATUS_ICON[data.status as StepStatus] : ''
  const isRunning = data.status === 'running'
  const hasFailed = data.status === 'failed'
  const hasSucceeded = data.status === 'success'
  const stepIcon = STEP_ICONS[data.stepType as string] ?? '○'

  const isFormatConvert = data.stepType === 'transform_format'
  const isConnector = data.stepType === 'connector_read' || data.stepType === 'connector_write'
  const cfg = (data.config as Record<string, unknown>) ?? {}
  const connectorId = (cfg.connector_id as string) || ''
  const isConfigured = isConnector && connectorId && !!(cfg._connected)

  // For file connector: derive the actual format from the object or output_format config
  const fileFormatExt = (() => {
    if (connectorId !== 'file') return null
    // write_per_source: explicit output_format wins
    const outFmt = (cfg.output_format as string) || ''
    if (outFmt) return outFmt.startsWith('.') ? outFmt : `.${outFmt}`
    // single file: use the extension of cfg.object
    const obj = (cfg.object as string) || ''
    const glob = obj.match(/\*\.([a-z0-9]+)/i)
    if (glob) return `.${glob[1]}`
    const dot = obj.lastIndexOf('.')
    if (dot > 0) return obj.slice(dot)
    return null
  })()

  // Format-specific colors so CSV→JSON is visually distinct on the canvas
  const FORMAT_COLORS: Record<string, string> = {
    '.csv':     '#10B981',   // green
    '.json':    '#F59E0B',   // amber
    '.parquet': '#8B5CF6',   // purple
    '.xlsx':    '#3B82F6',   // blue
  }

  // Resolved badge label, subtitle, and accent color
  const connIcon = (() => {
    if (fileFormatExt) return fileFormatExt.slice(1).toUpperCase()
    return connectorId ? CONNECTOR_ICONS[connectorId] ?? connectorId.toUpperCase().slice(0, 4) : ''
  })()

  const connLabel = (() => {
    if (fileFormatExt) return `${fileFormatExt.slice(1).toUpperCase()} File`
    return connectorId ? CONNECTOR_LABELS[connectorId] ?? connectorId : ''
  })()

  const connColor = (() => {
    if (fileFormatExt) return FORMAT_COLORS[fileFormatExt] ?? CONNECTOR_COLORS['file']
    return connectorId ? CONNECTOR_COLORS[connectorId] ?? 'var(--node-connector)' : ''
  })()

  // Object / file hint (truncated)
  const objHint = (() => {
    if (!connectorId) return ''
    const obj = (cfg.object as string) || ''
    const outFmt = (cfg.output_format as string) || ''
    const basePath = ((cfg.conn as Record<string,string>)?.base_path) || ''
    // write_per_source with format override
    if (!obj && outFmt) return `→ ${outFmt} per file`
    if (obj) return obj.length > 18 ? '…' + obj.slice(-16) : obj
    if (basePath) {
      const parts = basePath.replace(/\/$/, '').split('/')
      return parts[parts.length - 1] || basePath
    }
    return ''
  })()

  // Format Convert: derive input/output format badges
  const fmtIn  = ((cfg.input_format  as string) || '').replace(/^\./, '')
  const fmtOut = ((cfg.output_format as string) || '').replace(/^\./, '')
  const fmtInColor  = fmtIn  ? (FORMAT_COLORS[`.${fmtIn}`]  ?? 'var(--node-transform)') : 'var(--node-transform)'
  const fmtOutColor = fmtOut ? (FORMAT_COLORS[`.${fmtOut}`] ?? 'var(--node-transform)') : 'var(--node-transform)'
  const isFormatConfigured = isFormatConvert && !!(fmtIn && fmtOut)

  return (
    <div
      className={clsx('base-node', {
        'base-node--selected': selected,
        'base-node--running': isRunning,
        'base-node--failed': hasFailed,
        'base-node--success': hasSucceeded,
        'base-node--configured': isConfigured || isFormatConfigured,
        'base-node--unconfigured': isConnector && !isConfigured,
      })}
      style={{ '--node-color': isConfigured ? connColor : color } as React.CSSProperties}
    >
      <Handle type="target" position={Position.Left} />

      <div className="base-node__accent" />

      <div className="base-node__inner">
        {/* Format Convert node: two badges with arrow */}
        {isFormatConvert ? (
          isFormatConfigured ? (
            <span className="base-node__fmt-convert">
              <span className="base-node__conn-badge base-node__conn-badge--sm" style={{ background: fmtInColor }}>{fmtIn.toUpperCase()}</span>
              <span className="base-node__fmt-arrow">→</span>
              <span className="base-node__conn-badge base-node__conn-badge--sm" style={{ background: fmtOutColor }}>{fmtOut.toUpperCase()}</span>
            </span>
          ) : (
            <span className="base-node__icon" title="Format Convert">⇄</span>
          )
        ) : isConfigured ? (
          <span
            className="base-node__conn-badge"
            style={{ background: connColor }}
            title={connLabel}
          >
            {connIcon}
          </span>
        ) : (
          <span className="base-node__icon" title={data.stepType as string}>{stepIcon}</span>
        )}

        <div className="base-node__text">
          <span className="base-node__label">{data.label as string}</span>
          {isConfigured ? (
            <span className="base-node__conn-meta">
              <span className="base-node__conn-name">{connLabel}</span>
              {objHint && <span className="base-node__conn-obj">{objHint}</span>}
            </span>
          ) : (
            <span className="base-node__type">
              {data.stepType === 'connector_read' ? 'SOURCE'
                : data.stepType === 'connector_write' ? 'TARGET'
                : (data.stepType as string).replace(/_/g, ' ').toUpperCase()}
            </span>
          )}
        </div>

        {/* Configured checkmark */}
        {isConfigured && !statusIcon && (
          <span className="base-node__ready" title="Configured">●</span>
        )}

        {statusIcon && (
          <span
            className={clsx('base-node__status', `base-node__status--${data.status}`)}
            title={data.status as string}
          >
            {statusIcon}
          </span>
        )}
      </div>

      {/* Unconfigured prompt */}
      {isConnector && !connectorId && (
        <div className="base-node__prompt">Click to configure</div>
      )}

      {/* Partially configured (connector picked but not connected) */}
      {isConnector && connectorId && !cfg._connected && (
        <div className="base-node__prompt base-node__prompt--partial">
          <span
            className="base-node__conn-badge base-node__conn-badge--sm"
            style={{ background: connColor }}
          >{connIcon}</span>
          {connLabel} · finish setup
        </div>
      )}

      {data.rowsOut !== undefined && (
        <div className="base-node__rows">{(data.rowsOut as number).toLocaleString()} rows</div>
      )}

      {hasFailed && data.error && (
        <div className="base-node__error" title={data.error as string}>
          {(data.error as string).slice(0, 60)}{(data.error as string).length > 60 ? '…' : ''}
        </div>
      )}

      <Handle type="source" position={Position.Right} />
    </div>
  )
})

BaseNode.displayName = 'BaseNode'
