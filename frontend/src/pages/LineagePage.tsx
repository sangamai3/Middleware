import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  type Node,
  type Edge,
  Handle,
  Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { lineageApi, type LineageEdge } from '@/api/lineage'
import { flowsApi } from '@/api/flows'
import './LineagePage.css'

// ─── Custom node types ────────────────────────────────────────────────────────

type LineageNodeData = {
  connectorId?: string
  objectName?: string
  connectionId?: string
  label?: string
  totalEdges?: number
}

function LineageSourceNode({ data }: { data: LineageNodeData }) {
  return (
    <div className="ln-node ln-node--source">
      <div className="ln-node__connector">{data.connectorId}</div>
      <div className="ln-node__object">{data.objectName}</div>
      {data.connectionId && (
        <div className="ln-node__conn">{data.connectionId}</div>
      )}
      <Handle type="source" position={Position.Right} className="ln-handle" />
    </div>
  )
}

function LineageFlowNode({ data }: { data: LineageNodeData }) {
  const edges = data.totalEdges ?? 0
  return (
    <div className="ln-node ln-node--flow">
      <Handle type="target" position={Position.Left} className="ln-handle" />
      <div className="ln-node__flow-label">{data.label}</div>
      <div className="ln-node__flow-sub">{edges} edge{edges !== 1 ? 's' : ''}</div>
      <Handle type="source" position={Position.Right} className="ln-handle" />
    </div>
  )
}

function LineageSinkNode({ data }: { data: LineageNodeData }) {
  return (
    <div className="ln-node ln-node--sink">
      <Handle type="target" position={Position.Left} className="ln-handle" />
      <div className="ln-node__connector">{data.connectorId}</div>
      <div className="ln-node__object">{data.objectName}</div>
      {data.connectionId && (
        <div className="ln-node__conn">{data.connectionId}</div>
      )}
    </div>
  )
}

const nodeTypes = {
  lineageSource: LineageSourceNode,
  lineageFlow: LineageFlowNode,
  lineageSink: LineageSinkNode,
}

// ─── Graph component ──────────────────────────────────────────────────────────

function LineageGraph({ flowId, flowName }: { flowId: string; flowName: string }) {
  const { data: lineage, isLoading, isError } = useQuery({
    queryKey: ['lineage', flowId],
    queryFn: () => lineageApi.getFlowLineage(flowId),
    enabled: !!flowId,
    retry: false,
  })

  const { nodes, edges } = useMemo<{ nodes: Node<LineageNodeData>[]; edges: Edge[] }>(() => {
    if (!lineage) return { nodes: [], edges: [] }

    const srcCount = lineage.sources.length
    const sinkCount = lineage.sinks.length
    const maxSide = Math.max(srcCount, sinkCount, 1)
    const rowH = 110
    const totalH = maxSide * rowH
    const centerY = totalH / 2 - 40

    const nodes: Node<LineageNodeData>[] = [
      {
        id: 'flow',
        type: 'lineageFlow',
        position: { x: 310, y: centerY },
        data: { label: flowName || flowId, totalEdges: lineage.total_edges },
        draggable: true,
      },
    ]

    const edges: Edge[] = []

    lineage.sources.forEach((src: LineageEdge, i: number) => {
      const id = `src_${i}`
      const y = (i + 0.5) * (totalH / Math.max(srcCount, 1)) - 40
      nodes.push({
        id,
        type: 'lineageSource',
        position: { x: 20, y },
        data: {
          connectorId: src.connector_id,
          objectName: src.object_name,
          connectionId: src.connection_id,
        },
        draggable: true,
      })
      edges.push({
        id: `e_${id}`,
        source: id,
        target: 'flow',
        animated: true,
        style: { stroke: 'var(--accent)', strokeWidth: 1.5 },
        type: 'smoothstep',
      })
    })

    lineage.sinks.forEach((sink: LineageEdge, i: number) => {
      const id = `sink_${i}`
      const y = (i + 0.5) * (totalH / Math.max(sinkCount, 1)) - 40
      nodes.push({
        id,
        type: 'lineageSink',
        position: { x: 600, y },
        data: {
          connectorId: sink.connector_id,
          objectName: sink.object_name,
          connectionId: sink.connection_id,
        },
        draggable: true,
      })
      edges.push({
        id: `e_${id}`,
        source: 'flow',
        target: id,
        animated: true,
        style: { stroke: '#16a34a', strokeWidth: 1.5 },
        type: 'smoothstep',
      })
    })

    return { nodes, edges }
  }, [lineage, flowId, flowName])

  if (isLoading) {
    return <div className="lineage-rf-loading">Loading lineage…</div>
  }

  if (isError) {
    return (
      <div className="lineage-rf-empty">
        No lineage data available for this flow yet.<br />
        Run the flow first to generate lineage records.
      </div>
    )
  }

  if (!lineage) return null

  if (lineage.total_edges === 0) {
    return (
      <div className="lineage-rf-empty">
        This flow has no recorded source or sink edges yet.<br />
        Run the flow to populate lineage.
      </div>
    )
  }

  return (
    <div className="lineage-rf-wrap">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border)" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function LineagePage() {
  const [selectedFlow, setSelectedFlow] = useState<string>('')
  const [impactQuery, setImpactQuery] = useState({ connection_id: '', connector_id: '', object_name: '' })
  const [runImpact, setRunImpact] = useState(false)

  const { data: flows = [] } = useQuery({
    queryKey: ['flows'],
    queryFn: () => flowsApi.list(),
  })

  const { data: impact } = useQuery({
    queryKey: ['impact', impactQuery],
    queryFn: () => lineageApi.impactAnalysis(impactQuery),
    enabled: runImpact,
    retry: false,
  })

  const selectedFlowName =
    (flows as { flow_id: string; name?: string }[]).find((f) => f.flow_id === selectedFlow)?.name ?? selectedFlow

  return (
    <div className="lineage">
      <div className="lineage__header">
        <div>
          <h1 className="lineage__title">Data Lineage</h1>
          <p className="lineage__sub">Trace data sources, sinks, and downstream impact across flows.</p>
        </div>
        <select
          className="lineage-select"
          value={selectedFlow}
          onChange={(e) => setSelectedFlow(e.target.value)}
        >
          <option value="">Select a flow…</option>
          {(flows as { flow_id: string; name?: string }[]).map((f) => (
            <option key={f.flow_id} value={f.flow_id}>{f.name || f.flow_id}</option>
          ))}
        </select>
      </div>

      <div className="lineage__body">
        {/* React Flow graph */}
        <section className="lineage-graph-panel">
          {!selectedFlow ? (
            <div className="lineage-rf-empty lineage-rf-empty--center">
              Select a flow above to visualize its data lineage.
            </div>
          ) : (
            <ReactFlowProvider>
              <LineageGraph flowId={selectedFlow} flowName={selectedFlowName} />
            </ReactFlowProvider>
          )}
        </section>

        {/* Impact analysis sidebar */}
        <section className="lineage-impact-panel">
          <div className="lineage-panel__title">Impact Analysis</div>
          <p className="lineage-panel__desc">
            Find all flows affected by a connection, connector, or object change.
          </p>

          <div className="impact-form">
            <div className="impact-field">
              <label>Connection ID</label>
              <input
                className="impact-input"
                placeholder="conn_salesforce_prod"
                value={impactQuery.connection_id}
                onChange={(e) => setImpactQuery((q) => ({ ...q, connection_id: e.target.value }))}
              />
            </div>
            <div className="impact-field">
              <label>Connector ID</label>
              <input
                className="impact-input"
                placeholder="salesforce"
                value={impactQuery.connector_id}
                onChange={(e) => setImpactQuery((q) => ({ ...q, connector_id: e.target.value }))}
              />
            </div>
            <div className="impact-field">
              <label>Object name</label>
              <input
                className="impact-input"
                placeholder="Account"
                value={impactQuery.object_name}
                onChange={(e) => setImpactQuery((q) => ({ ...q, object_name: e.target.value }))}
              />
            </div>
            <button className="impact-btn" onClick={() => setRunImpact(true)}>
              Analyze impact
            </button>
          </div>

          {impact && (
            <div className="impact-result">
              <div className="impact-result__head">
                {impact.count} affected flow{impact.count !== 1 ? 's' : ''}
              </div>
              {impact.affected_flows.length === 0 ? (
                <div className="lineage-empty">No flows affected.</div>
              ) : (
                <ul className="impact-list">
                  {impact.affected_flows.map((fid) => (
                    <li key={fid} className="impact-list__item">{fid}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
