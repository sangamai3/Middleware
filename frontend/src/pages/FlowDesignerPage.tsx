import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ReactFlowProvider } from '@xyflow/react'
import type { Edge } from '@xyflow/react'
import { flowsApi } from '@/api/flows'
import { useFlowStore } from '@/store/flowStore'
import { useCanvasStore } from '@/store/canvasStore'
import type { CanvasNode } from '@/components/nodes/BaseNode'
import type { NodeFamily, StepConfig } from '@/types'
import { Toolbar } from '@/components/canvas/Toolbar'
import { NodePalette } from '@/components/canvas/NodePalette'
import { FlowCanvas } from '@/components/canvas/FlowCanvas'
import { ConfigPanel } from '@/components/panels/ConfigPanel'
import './FlowDesignerPage.css'

const STEP_META: Record<string, { label: string; family: NodeFamily }> = {
  scheduler:         { label: 'Scheduler',     family: 'trigger' },
  webhook_trigger:   { label: 'Webhook',       family: 'trigger' },
  streaming_trigger: { label: 'Streaming',     family: 'trigger' },
  event_trigger:     { label: 'Event',         family: 'trigger' },
  connector_read:    { label: 'Source',        family: 'connector' },
  connector_write:   { label: 'Target',        family: 'connector' },
  transform_map:     { label: 'Map Fields',    family: 'transform' },
  transform_filter:  { label: 'Filter',        family: 'transform' },
  transform_sql:     { label: 'SQL',           family: 'transform' },
  transform_script:  { label: 'Script',        family: 'transform' },
  router:            { label: 'Router',        family: 'control' },
  merge:             { label: 'Merge',         family: 'control' },
  iterator:          { label: 'Iterator',      family: 'control' },
  sub_flow:          { label: 'Sub-flow',      family: 'control' },
  set_variable:      { label: 'Set Variable',  family: 'utility' },
  logger:            { label: 'Logger',        family: 'utility' },
  approval:          { label: 'Approval',      family: 'utility' },
  notification:      { label: 'Notification',  family: 'utility' },
  sync_endpoint:     { label: 'Sync Endpoint', family: 'utility' },
}

function stepsToCanvas(steps: StepConfig[]): { nodes: CanvasNode[]; edges: Edge[] } {
  // Topological sort for sensible left-to-right layout
  const order: string[] = []
  const visited = new Set<string>()
  const visit = (id: string) => {
    if (visited.has(id)) return
    visited.add(id)
    const step = steps.find((s) => s.id === id)
    step?.depends_on.forEach(visit)
    order.push(id)
  }
  steps.forEach((s) => visit(s.id))

  const nodes: CanvasNode[] = order.map((id, i) => {
    const step = steps.find((s) => s.id === id)!
    const meta = STEP_META[step.type] ?? { label: step.type.replace(/_/g, ' '), family: 'utility' as NodeFamily }
    return {
      id: step.id,
      type: 'default',
      position: { x: 80 + i * 220, y: 180 },
      data: {
        label: (step.config.label as string) || meta.label,
        stepType: step.type,
        family: meta.family,
        config: step.config,
      },
    }
  })

  const edges: Edge[] = steps.flatMap((step) =>
    step.depends_on.map((src) => ({
      id: `e-${src}-${step.id}`,
      source: src,
      target: step.id,
      animated: false,
    }))
  )

  return { nodes, edges }
}

export function FlowDesignerPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentFlow, setFlow } = useFlowStore()
  const { setNodes, setEdges, selectedNodeId } = useCanvasStore()

  useEffect(() => {
    if (!id) return
    flowsApi.get(id)
      .then((flow) => {
        setFlow(flow)
        const { nodes, edges } = stepsToCanvas(flow.steps ?? [])
        setNodes(nodes)
        setEdges(edges)
      })
      .catch(() => navigate('/flows'))
  }, [id])

  const flowId = currentFlow?.flow_id ?? id ?? ''
  const flowName = currentFlow?.name ?? ''

  return (
    <ReactFlowProvider>
      <div className="designer">
        <Toolbar flowId={flowId} flowName={flowName} />
        <div className="designer__body">
          <NodePalette />
          <FlowCanvas />
          {selectedNodeId && <ConfigPanel />}
        </div>
      </div>
    </ReactFlowProvider>
  )
}
