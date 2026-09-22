import { useCallback } from 'react'
import type { NodeFamily } from '@/types'
import './NodePalette.css'

interface PaletteItem {
  stepType: string
  label: string
  family: NodeFamily
}

const PALETTE: { group: string; items: PaletteItem[] }[] = [
  {
    group: 'Triggers',
    items: [
      { stepType: 'scheduler', label: 'Scheduler', family: 'trigger' },
      { stepType: 'webhook_trigger', label: 'Webhook', family: 'trigger' },
      { stepType: 'streaming_trigger', label: 'Streaming', family: 'trigger' },
      { stepType: 'event_trigger', label: 'Event', family: 'trigger' },
    ],
  },
  {
    group: 'Connectors',
    items: [
      { stepType: 'connector_read', label: 'Source', family: 'connector' },
      { stepType: 'connector_write', label: 'Target', family: 'connector' },
    ],
  },
  {
    group: 'Transform',
    items: [
      { stepType: 'transform_format', label: 'Format Convert', family: 'transform' },
      { stepType: 'transform_map', label: 'Map Fields', family: 'transform' },
      { stepType: 'transform_filter', label: 'Filter', family: 'transform' },
      { stepType: 'transform_sql', label: 'SQL', family: 'transform' },
      { stepType: 'transform_script', label: 'Script', family: 'transform' },
    ],
  },
  {
    group: 'Control',
    items: [
      { stepType: 'router', label: 'Router', family: 'control' },
      { stepType: 'merge', label: 'Merge', family: 'control' },
      { stepType: 'iterator', label: 'Iterator', family: 'control' },
      { stepType: 'sub_flow', label: 'Sub-flow', family: 'control' },
    ],
  },
  {
    group: 'Utility',
    items: [
      { stepType: 'set_variable', label: 'Set Variable', family: 'utility' },
      { stepType: 'logger', label: 'Logger', family: 'utility' },
      { stepType: 'approval', label: 'Approval', family: 'utility' },
      { stepType: 'notification', label: 'Notification', family: 'utility' },
      { stepType: 'sync_endpoint', label: 'Sync Endpoint', family: 'utility' },
    ],
  },
]

const FAMILY_COLOR: Record<NodeFamily, string> = {
  trigger: 'var(--node-trigger)',
  connector: 'var(--node-connector)',
  transform: 'var(--node-transform)',
  control: 'var(--node-control)',
  utility: 'var(--node-utility)',
}

interface Props {
  onDragStart?: (item: PaletteItem) => void
}

export function NodePalette({ onDragStart }: Props) {
  const handleDragStart = useCallback(
    (e: React.DragEvent, item: PaletteItem) => {
      e.dataTransfer.setData('application/sangam-node', JSON.stringify(item))
      e.dataTransfer.effectAllowed = 'copy'
      onDragStart?.(item)
    },
    [onDragStart],
  )

  return (
    <aside className="node-palette">
      <div className="node-palette__header">Node Types</div>
      <div className="node-palette__scroll">
        {PALETTE.map((section) => (
          <div key={section.group} className="node-palette__section">
            <div className="node-palette__group">{section.group}</div>
            {section.items.map((item) => (
              <div
                key={item.stepType}
                className="node-palette__item"
                draggable
                onDragStart={(e) => handleDragStart(e, item)}
                style={{ '--item-color': FAMILY_COLOR[item.family] } as React.CSSProperties}
              >
                <span className="node-palette__dot" />
                {item.label}
              </div>
            ))}
          </div>
        ))}
      </div>
    </aside>
  )
}
