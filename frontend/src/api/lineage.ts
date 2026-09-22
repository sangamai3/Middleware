import { api } from './client'

export interface LineageEdge {
  direction: 'read' | 'write'
  connection_id: string
  connector_id: string
  object_name: string
  step_id: string
  run_id?: string
}

export interface FlowLineage {
  flow_id: string
  sources: LineageEdge[]
  sinks: LineageEdge[]
  total_edges: number
}

export interface ImpactResult {
  query: Record<string, string | null>
  affected_flows: string[]
  count: number
}

export const lineageApi = {
  getFlowLineage: (flowId: string) =>
    api.get<FlowLineage>(`/lineage/${flowId}`),
  impactAnalysis: (params: {
    connection_id?: string
    connector_id?: string
    object_name?: string
  }) => {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(params).filter(([, v]) => v != null) as [string, string][]
      )
    ).toString()
    return api.get<ImpactResult>(`/lineage/impact${qs ? `?${qs}` : ''}`)
  },
}
