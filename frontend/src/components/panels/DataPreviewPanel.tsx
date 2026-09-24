import { useState } from 'react'
import { flowsApi, type FlowPreviewResult } from '@/api/flows'
import { beautifyPreviewContent } from '@/lib/beautifyPreview'
import { buildFlowDefinition } from '@/lib/flowDefinition'
import type { CanvasNode } from '@/components/nodes/BaseNode'
import type { Edge } from '@xyflow/react'
import './DataPreviewPanel.css'

const PREVIEW_STEP_TYPES = new Set([
  'connector_read',
  'connector_write',
  'transform_format',
  'transform_map',
  'transform_filter',
  'transform_sql',
  'transform_script',
  'merge',
  'router',
])

interface Props {
  flowId: string
  flowName: string
  stepId: string
  stepType: string
  stepLabel: string
  nodes: CanvasNode[]
  edges: Edge[]
  onColumns?: (cols: { name: string; data_type: string }[]) => void
}

export function DataPreviewPanel({
  flowId,
  flowName,
  stepId,
  stepType,
  stepLabel,
  nodes,
  edges,
  onColumns,
}: Props) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<FlowPreviewResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!PREVIEW_STEP_TYPES.has(stepType)) {
    return null
  }

  const runPreview = async () => {
    setLoading(true)
    setError(null)
    try {
      const definition = buildFlowDefinition(flowId, flowName, nodes, edges)
      const data = await flowsApi.preview(definition, stepId, 25)
      if (data.error) {
        setError(data.error)
        setResult(data)
      } else {
        setResult(data)
        if (data.columns?.length) onColumns?.(data.columns)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Preview failed')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const cols = result?.columns ?? []
  const rows = result?.rows ?? []

  return (
    <div className="data-preview">
      <div className="data-preview__head">
        <span className="data-preview__title">Data preview</span>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={runPreview}
          disabled={loading}
        >
          {loading ? 'Running…' : 'Preview'}
        </button>
      </div>
      <p className="data-preview__hint">
        Runs upstream steps through <strong>{stepLabel}</strong> (target writes are skipped).
      </p>

      {error && <div className="data-preview__error">{error}</div>}

      {result && !error && cols.length > 0 && (
        <>
          <div className="data-preview__meta">
            {result.row_count} row{result.row_count === 1 ? '' : 's'}
            {result.truncated ? ` · showing first ${result.preview_row_count}` : ''}
            {result.steps_executed?.length ? (
              <span className="data-preview__chain" title={result.steps_executed.join(' → ')}>
                · {result.steps_executed.length} step{result.steps_executed.length === 1 ? '' : 's'} executed
              </span>
            ) : null}
          </div>

          <div className="data-preview__section-title">
            {result.input_format || result.output_format
              ? `Input (${(result.input_format || 'table').toUpperCase()})`
              : 'Rows (in-memory)'}
          </div>
          <div className="ccn-preview-wrap">
            <table className="ccn-preview-table">
              <thead>
                <tr>
                  {cols.slice(0, 12).map((c) => (
                    <th key={c.name} title={c.data_type}>{c.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i}>
                    {cols.slice(0, 12).map((c) => (
                      <td key={c.name}>{formatCell(row[c.name])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {result.formatted_output && (
            <>
              <div className="data-preview__section-title data-preview__section-title--out">
                Output preview — {result.formatted_output.label}
                {result.formatted_output.truncated ? ' (first rows)' : ''}
              </div>
              <pre className="data-preview__serialized">
                {beautifyPreviewContent(
                  result.formatted_output.content,
                  result.formatted_output.format,
                )}
              </pre>
            </>
          )}
        </>
      )}

      {result && !error && cols.length === 0 && !loading && (
        <div className="data-preview__empty">No rows returned.</div>
      )}
    </div>
  )
}

function formatCell(val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'object') {
    try {
      return JSON.stringify(val, null, 2)
    } catch {
      return String(val)
    }
  }
  return String(val)
}
