import { useCallback, useState } from 'react'
import { useCanvasStore } from '@/store/canvasStore'
import { useFlowStore } from '@/store/flowStore'
import { flowsApi } from '@/api/flows'
import { subscribeToRun } from '@/api/client'
import type { FlowDefinition, StepConfig } from '@/types'
import clsx from 'clsx'
import './Toolbar.css'

function buildFlowDefinition(flowId: string, name: string, nodes: ReturnType<typeof useCanvasStore.getState>['nodes'], edges: ReturnType<typeof useCanvasStore.getState>['edges']): FlowDefinition {
  const steps: StepConfig[] = nodes.map((n) => {
    const deps = edges.filter((e) => e.target === n.id).map((e) => e.source)
    return {
      id: n.id,
      type: n.data.stepType,
      config: n.data.config,
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

interface Props {
  flowId: string
  flowName: string
}

export function Toolbar({ flowId, flowName }: Props) {
  const { nodes, edges, isRunning, setRunning, setRunId, applyFlowEvent, resetRunState } = useCanvasStore()
  const { isDirty, markClean } = useFlowStore()
  const [status, setStatus] = useState<string>('')
  const [saving, setSaving] = useState(false)

  const handleSave = useCallback(async () => {
    setSaving(true)
    setStatus('Saving…')
    try {
      const definition = buildFlowDefinition(flowId, flowName, nodes, edges)
      await flowsApi.update(flowId, definition)
      markClean()
      setStatus('Saved')
      setTimeout(() => setStatus(''), 2000)
    } catch (err) {
      setStatus('Save failed')
    } finally {
      setSaving(false)
    }
  }, [flowId, flowName, nodes, edges, markClean])

  const handleRun = useCallback(async () => {
    if (isRunning) return
    setStatus('Starting…')
    resetRunState()
    try {
      const definition = buildFlowDefinition(flowId, flowName, nodes, edges)
      await flowsApi.update(flowId, definition)
      const result = await flowsApi.execute(flowId)
      setRunId(result.run_id)
      setRunning(true)
      setStatus('Running')

      const cleanup = subscribeToRun(
        result.run_id,
        (event) => applyFlowEvent(event),
        () => {
          setRunning(false)
          cleanup()
          setStatus('Done')
          setTimeout(() => setStatus(''), 3000)
        },
      )
    } catch (err) {
      setStatus('Run failed')
      setRunning(false)
    }
  }, [flowId, flowName, nodes, edges, isRunning, setRunning, setRunId, applyFlowEvent, resetRunState])

  const handleValidate = useCallback(async () => {
    setStatus('Validating…')
    try {
      const definition = buildFlowDefinition(flowId, flowName, nodes, edges)
      await flowsApi.update(flowId, definition)
      const result = await flowsApi.validate(flowId)
      if (result.valid) {
        setStatus(result.warnings?.length ? `Valid (${result.warnings.length} warnings)` : 'Valid ✓')
      } else {
        setStatus(`Invalid: ${result.error}`)
      }
      setTimeout(() => setStatus(''), 4000)
    } catch {
      setStatus('Validation error')
    }
  }, [flowId, flowName, nodes, edges])

  return (
    <div className="toolbar">
      <div className="toolbar__left">
        <span className="toolbar__flow-name">{flowName}</span>
        {isDirty && <span className="toolbar__dirty">●</span>}
      </div>

      <div className="toolbar__center">
        {status && <span className="toolbar__status">{status}</span>}
      </div>

      <div className="toolbar__right">
        <button
          className="toolbar__btn toolbar__btn--ghost"
          onClick={handleValidate}
          disabled={nodes.length === 0}
          title="Validate flow"
        >
          Validate
        </button>
        <button
          className="toolbar__btn toolbar__btn--ghost"
          onClick={handleSave}
          disabled={saving || !isDirty}
          title="Save flow"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          className={clsx('toolbar__btn toolbar__btn--run', { 'toolbar__btn--running': isRunning })}
          onClick={handleRun}
          disabled={isRunning || nodes.length === 0}
          title={isRunning ? 'Running…' : 'Run flow'}
        >
          {isRunning ? '⟳ Running' : '▶ Run'}
        </button>
      </div>
    </div>
  )
}
