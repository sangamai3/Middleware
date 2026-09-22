import { useCanvasStore } from '@/store/canvasStore'
import type { CanvasNodeData } from '@/types'
import { ConnectorNodeConfig } from './ConnectorNodeConfig'
import './ConfigPanel.css'

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
