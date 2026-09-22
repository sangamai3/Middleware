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
  transform_map: '⇌', transform_filter: '⧉', transform_sql: '◧', transform_script: '{ }',
  router: '⑂', merge: '⑃', iterator: '⟲', sub_flow: '▣',
  set_variable: 'x=', logger: '☰', approval: '✓?', notification: '🔔', sync_endpoint: '⇋',
  global_exception: '⚠', component_exception: '⚠',
}

export type CanvasNode = Node<CanvasNodeData>

export const BaseNode = memo(({ data, selected }: NodeProps<CanvasNode>) => {
  const color = FAMILY_COLOR[data.family as NodeFamily]
  const statusIcon = data.status ? STATUS_ICON[data.status as StepStatus] : ''
  const isRunning = data.status === 'running'
  const hasFailed = data.status === 'failed'
  const hasSucceeded = data.status === 'success'
  const stepIcon = STEP_ICONS[data.stepType as string] ?? '○'

  return (
    <div
      className={clsx('base-node', {
        'base-node--selected': selected,
        'base-node--running': isRunning,
        'base-node--failed': hasFailed,
        'base-node--success': hasSucceeded,
      })}
      style={{ '--node-color': color } as React.CSSProperties}
    >
      <Handle type="target" position={Position.Left} />

      <div className="base-node__accent" />

      <div className="base-node__inner">
        <span className="base-node__icon" title={data.stepType as string}>{stepIcon}</span>
        <div className="base-node__text">
          <span className="base-node__label">{data.label as string}</span>
          <span className="base-node__type">
            {data.stepType === 'connector_read' ? 'SOURCE'
              : data.stepType === 'connector_write' ? 'TARGET'
              : (data.stepType as string).replace(/_/g, ' ').toUpperCase()}
          </span>
        </div>
        {statusIcon && (
          <span
            className={clsx('base-node__status', `base-node__status--${data.status}`)}
            title={data.status as string}
          >
            {statusIcon}
          </span>
        )}
      </div>

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
