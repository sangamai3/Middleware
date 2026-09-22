import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { lineageApi, type LineageEdge } from '@/api/lineage'
import { flowsApi } from '@/api/flows'
import './LineagePage.css'

export function LineagePage() {
  const [selectedFlow, setSelectedFlow] = useState<string>('')
  const [impactQuery, setImpactQuery] = useState({ connection_id: '', connector_id: '', object_name: '' })
  const [runImpact, setRunImpact] = useState(false)

  const { data: flows = [] } = useQuery({
    queryKey: ['flows'],
    queryFn: () => flowsApi.list(),
  })

  const { data: lineage, isLoading: lineageLoading } = useQuery({
    queryKey: ['lineage', selectedFlow],
    queryFn: () => lineageApi.getFlowLineage(selectedFlow),
    enabled: !!selectedFlow,
    retry: false,
  })

  const { data: impact } = useQuery({
    queryKey: ['impact', impactQuery],
    queryFn: () => lineageApi.impactAnalysis(impactQuery),
    enabled: runImpact,
    retry: false,
  })

  return (
    <div className="lineage">
      <div className="lineage__header">
        <h1 className="lineage__title">Data Lineage</h1>
        <p className="lineage__sub">Trace data sources, sinks, and downstream impact across flows.</p>
      </div>

      <div className="lineage__panels">
        {/* Flow lineage */}
        <section className="lineage-panel">
          <div className="lineage-panel__head">
            <h2 className="lineage-panel__title">Flow Lineage</h2>
            <select
              className="lineage-select"
              value={selectedFlow}
              onChange={e => setSelectedFlow(e.target.value)}
            >
              <option value="">Select a flow…</option>
              {flows.map((f: any) => (
                <option key={f.flow_id} value={f.flow_id}>{f.name || f.flow_id}</option>
              ))}
            </select>
          </div>

          {lineageLoading && <div className="lineage-loading">Loading lineage…</div>}

          {lineage && !lineageLoading && (
            <div className="lineage-graph">
              <div className="lineage-graph__col">
                <div className="lineage-col-label">Sources</div>
                {lineage.sources.length === 0
                  ? <div className="lineage-empty">No sources</div>
                  : lineage.sources.map((e, i) => <EdgeCard key={i} edge={e} direction="source" />)
                }
              </div>
              <div className="lineage-graph__arrow">
                <div className="lineage-flow-node">
                  <div className="lineage-flow-node__id">{lineage.flow_id}</div>
                  <div className="lineage-flow-node__sub">{lineage.total_edges} edge{lineage.total_edges !== 1 ? 's' : ''}</div>
                </div>
              </div>
              <div className="lineage-graph__col">
                <div className="lineage-col-label">Sinks</div>
                {lineage.sinks.length === 0
                  ? <div className="lineage-empty">No sinks</div>
                  : lineage.sinks.map((e, i) => <EdgeCard key={i} edge={e} direction="sink" />)
                }
              </div>
            </div>
          )}

          {!selectedFlow && (
            <div className="lineage-empty lineage-empty--center">Select a flow above to see its data lineage.</div>
          )}
        </section>

        {/* Impact analysis */}
        <section className="lineage-panel">
          <div className="lineage-panel__head">
            <h2 className="lineage-panel__title">Impact Analysis</h2>
          </div>
          <p className="lineage-panel__desc">Find all flows affected by a connection, connector, or object change.</p>

          <div className="impact-form">
            <div className="impact-field">
              <label>Connection ID</label>
              <input
                className="impact-input"
                placeholder="conn_salesforce_prod"
                value={impactQuery.connection_id}
                onChange={e => setImpactQuery(q => ({ ...q, connection_id: e.target.value }))}
              />
            </div>
            <div className="impact-field">
              <label>Connector ID</label>
              <input
                className="impact-input"
                placeholder="salesforce"
                value={impactQuery.connector_id}
                onChange={e => setImpactQuery(q => ({ ...q, connector_id: e.target.value }))}
              />
            </div>
            <div className="impact-field">
              <label>Object name</label>
              <input
                className="impact-input"
                placeholder="Account"
                value={impactQuery.object_name}
                onChange={e => setImpactQuery(q => ({ ...q, object_name: e.target.value }))}
              />
            </div>
            <button
              className="impact-btn"
              onClick={() => setRunImpact(true)}
            >
              Analyze impact
            </button>
          </div>

          {impact && (
            <div className="impact-result">
              <div className="impact-result__head">
                {impact.count} affected flow{impact.count !== 1 ? 's' : ''}
              </div>
              {impact.affected_flows.length === 0
                ? <div className="lineage-empty">No flows affected.</div>
                : (
                  <ul className="impact-list">
                    {impact.affected_flows.map(fid => (
                      <li key={fid} className="impact-list__item">{fid}</li>
                    ))}
                  </ul>
                )
              }
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function EdgeCard({ edge, direction }: { edge: LineageEdge; direction: 'source' | 'sink' }) {
  return (
    <div className={`edge-card edge-card--${direction}`}>
      <div className="edge-card__connector">{edge.connector_id}</div>
      <div className="edge-card__object">{edge.object_name}</div>
      <div className="edge-card__conn">{edge.connection_id}</div>
      {edge.step_id && <div className="edge-card__step">step: {edge.step_id}</div>}
    </div>
  )
}
