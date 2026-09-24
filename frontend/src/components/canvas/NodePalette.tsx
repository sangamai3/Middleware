import { useCallback, useState } from 'react'
import type { NodeFamily } from '@/types'
import './NodePalette.css'

interface PaletteItem {
  stepType: string
  label: string
  family: NodeFamily
  tooltip?: string
}

const PALETTE: { group: string; items: PaletteItem[] }[] = [
  {
    group: 'Triggers',
    items: [
      { stepType: 'scheduler', label: 'Scheduler', family: 'trigger', tooltip: 'Run the flow on a cron schedule or fixed interval' },
      { stepType: 'webhook_trigger', label: 'Webhook', family: 'trigger', tooltip: 'Start the flow when an HTTP webhook fires' },
      { stepType: 'streaming_trigger', label: 'Streaming', family: 'trigger', tooltip: 'Subscribe to a Kafka/Kinesis stream and process each message batch' },
      { stepType: 'event_trigger', label: 'Event', family: 'trigger', tooltip: 'Trigger the flow from an internal platform event or bus message' },
    ],
  },
  {
    group: 'Connectors',
    items: [
      { stepType: 'connector_read', label: 'Source', family: 'connector', tooltip: 'Read data from a database, file, API, or cloud service' },
      { stepType: 'connector_write', label: 'Target', family: 'connector', tooltip: 'Write or upsert data into a destination system' },
    ],
  },
  {
    group: 'Transform',
    items: [
      { stepType: 'transform_format', label: 'Format Convert', family: 'transform', tooltip: 'Annotate the pipeline with an output format hint (CSV → JSON, Parquet, etc.)' },
      { stepType: 'transform_map', label: 'Map Fields', family: 'transform', tooltip: 'Rename, cast, and derive columns from the upstream DataFrame' },
      { stepType: 'transform_filter', label: 'Filter', family: 'transform', tooltip: 'Drop rows that do not match a condition expression' },
      { stepType: 'transform_sql', label: 'SQL', family: 'transform', tooltip: 'Run an arbitrary SQL SELECT on the upstream data using DuckDB' },
      { stepType: 'transform_script', label: 'Script', family: 'transform', tooltip: 'Apply a Python function to the DataFrame for custom transformations' },
    ],
  },
  {
    group: 'Control',
    items: [
      { stepType: 'router', label: 'Router', family: 'control', tooltip: 'Branch the flow into multiple paths based on a condition' },
      { stepType: 'merge', label: 'Merge', family: 'control', tooltip: 'Combine DataFrames from multiple upstream branches into one' },
      { stepType: 'iterator', label: 'Iterator', family: 'control', tooltip: 'Repeat a sub-flow once for each row or item in a list' },
      { stepType: 'sub_flow', label: 'Sub-flow', family: 'control', tooltip: 'Embed and invoke another flow as a reusable step' },
    ],
  },
  {
    group: 'Utility',
    items: [
      { stepType: 'set_variable', label: 'Set Variable', family: 'utility', tooltip: 'Assign a value to a flow variable for use in later steps' },
      { stepType: 'logger', label: 'Logger', family: 'utility', tooltip: 'Emit a structured log entry during execution for debugging' },
      { stepType: 'approval', label: 'Approval', family: 'utility', tooltip: 'Pause the flow and wait for a human to approve or reject' },
      { stepType: 'notification', label: 'Notification', family: 'utility', tooltip: 'Send a Slack, email, or webhook alert when reached' },
      { stepType: 'sync_endpoint', label: 'Sync Endpoint', family: 'utility', tooltip: 'Expose the flow as a synchronous REST endpoint that returns a response' },
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
  const [filter, setFilter] = useState('')

  const handleDragStart = useCallback(
    (e: React.DragEvent, item: PaletteItem) => {
      e.dataTransfer.setData('application/sangam-node', JSON.stringify(item))
      e.dataTransfer.effectAllowed = 'copy'
      onDragStart?.(item)
    },
    [onDragStart],
  )

  const q = filter.trim().toLowerCase()
  const filtered = q
    ? PALETTE.map((s) => ({ ...s, items: s.items.filter((i) => i.label.toLowerCase().includes(q)) })).filter((s) => s.items.length > 0)
    : PALETTE

  return (
    <aside className="node-palette">
      <div className="node-palette__header">Node Types</div>
      <div className="node-palette__search">
        <span className="node-palette__search-icon" aria-hidden>⌕</span>
        <input
          type="search"
          placeholder="Filter nodes…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter node types"
        />
      </div>
      <div className="node-palette__scroll">
        {filtered.length === 0 ? (
          <div className="node-palette__empty">No matches</div>
        ) : filtered.map((section) => (
          <div key={section.group} className="node-palette__section">
            <div className="node-palette__group">{section.group}</div>
            {section.items.map((item) => (
              <div
                key={item.stepType}
                className="node-palette__item"
                draggable
                onDragStart={(e) => handleDragStart(e, item)}
                style={{ '--item-color': FAMILY_COLOR[item.family] } as React.CSSProperties}
                title={item.tooltip}
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
