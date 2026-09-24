import { useEffect, useRef } from 'react'
import { buildFlowDefinition } from '@/lib/flowDefinition'
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
import { RunResultsPanel } from '@/components/canvas/RunResultsPanel'
import './FlowDesignerPage.css'

const STEP_META: Record<string, { label: string; family: NodeFamily }> = {
  scheduler:         { label: 'Scheduler',     family: 'trigger' },
  webhook_trigger:   { label: 'Webhook',       family: 'trigger' },
  streaming_trigger: { label: 'Streaming',     family: 'trigger' },
  event_trigger:     { label: 'Event',         family: 'trigger' },
  connector_read:    { label: 'Source',        family: 'connector' },
  connector_write:   { label: 'Target',        family: 'connector' },
  transform_format:  { label: 'Format Convert', family: 'transform' },
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
      type: step.type,
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
  const { currentFlow, setFlow, isDirty, markClean } = useFlowStore()
  const { nodes, edges, setNodes, setEdges } = useCanvasStore()
  const loadedFlowId = useRef<string | null>(null)

  useEffect(() => {
    if (!id) return
    loadedFlowId.current = null
    flowsApi.get(id)
      .then((flow) => {
        setFlow(flow)
        const { nodes, edges } = stepsToCanvas(flow.steps ?? [])
        setNodes(nodes)
        setEdges(edges)
        loadedFlowId.current = id
      })
      .catch(() => navigate('/flows'))
  }, [id, navigate, setFlow, setNodes, setEdges])

  const flowId = currentFlow?.flow_id ?? id ?? ''
  const flowName = currentFlow?.name ?? ''

  useEffect(() => {
    if (!flowId || !flowName || loadedFlowId.current !== flowId || !isDirty) return
    const timer = window.setTimeout(() => {
      const definition = buildFlowDefinition(flowId, flowName, nodes, edges)
      flowsApi.update(flowId, definition).then(() => markClean()).catch(() => {})
    }, 2000)
    return () => window.clearTimeout(timer)
  }, [flowId, flowName, nodes, edges, isDirty, markClean])

  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!isDirty) return
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [isDirty])

  return (
    <ReactFlowProvider>
      <div className="designer">
        <Toolbar
          flowId={flowId}
          flowName={flowName}
          initialStatus={currentFlow?.status}
        />
        <div className="designer__body">
          <NodePalette />
          <FlowCanvas />
          <ConfigPanel flowId={flowId} flowName={flowName} />
        </div>
        <RunResultsPanel />
      </div>
    </ReactFlowProvider>
  )
}
