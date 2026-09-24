import type { FlowDefinition, StepConfig } from '@/types'
import type { CanvasNode } from '@/components/nodes/BaseNode'
import type { Edge } from '@xyflow/react'

export function buildFlowDefinition(
  flowId: string,
  name: string,
  nodes: CanvasNode[],
  edges: Edge[],
): FlowDefinition {
  const steps: StepConfig[] = nodes.map((n) => {
    const deps = edges.filter((e) => e.target === n.id).map((e) => e.source)
    const config = { ...(n.data.config as Record<string, unknown>) }
    const label = String(n.data.label ?? '').trim()
    if (label) config.label = label

    return {
      id: n.id,
      type: n.data.stepType,
      config,
      depends_on: deps,
      retries: 0,
      retry_delay: 'exponential',
      retry_on: [],
      timeout_seconds: null,
      on_row_error: 'fail',
      optional: false,
    }
  })
  return {
    flow_id: flowId,
    name,
    description: '',
    version: '1',
    status: 'draft',
    trigger: 'manual',
    trigger_config: {},
    steps,
    variables: {},
    tags: [],
    created_at: undefined,
    updated_at: undefined,
    created_by: '',
  }
}
