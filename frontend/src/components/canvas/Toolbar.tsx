import { useCallback, useEffect, useMemo, useState } from 'react'
import { useCanvasStore } from '@/store/canvasStore'
import { useFlowStore } from '@/store/flowStore'
import { flowsApi, runsApi } from '@/api/flows'
import { subscribeToRun } from '@/api/client'
import { buildFlowDefinition } from '@/lib/flowDefinition'
import type { CanvasNode } from '@/components/nodes/BaseNode'
import clsx from 'clsx'
import { FlowDockerComposeModal } from './FlowDockerComposeModal'
import './Toolbar.css'

type ValidationResult = {
  valid: boolean
  warnings?: string[]
  error?: string
}

function humanizeWarnings(messages: string[], nodes: CanvasNode[]): string[] {
  return messages.map((msg) => {
    let out = msg
    for (const n of nodes) {
      const label = String(n.data.label ?? '').trim()
      if (label) {
        out = out.split(`'${n.id}'`).join(`'${label}'`)
      }
    }
    return out
  })
}

interface Props {
  flowId: string
  flowName: string
  initialStatus?: string
}

export function Toolbar({ flowId, flowName, initialStatus }: Props) {
  const {
    nodes,
    edges,
    isRunning,
    setRunning,
    setRunId,
    setRunResult,
    setRunPanelOpen,
    applyFlowEvent,
    resetRunState,
  } = useCanvasStore()
  const { isDirty, markClean } = useFlowStore()
  const [status, setStatus] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [validationPanelOpen, setValidationPanelOpen] = useState(false)
  const [deploying, setDeploying] = useState(false)
  const [showDockerCompose, setShowDockerCompose] = useState(false)
  const [flowStatus, setFlowStatus] = useState<string>(initialStatus ?? 'draft')

  useEffect(() => {
    if (initialStatus) setFlowStatus(initialStatus)
  }, [initialStatus, flowId])

  const warningLines = useMemo(
    () => humanizeWarnings(validation?.warnings ?? [], nodes),
    [validation?.warnings, nodes],
  )

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
    setRunResult(null)
    setRunPanelOpen(true)
    try {
      const definition = buildFlowDefinition(flowId, flowName, nodes, edges)
      await flowsApi.update(flowId, definition)
      const result = await flowsApi.execute(flowId)
      setRunId(result.run_id)
      setRunning(true)
      setStatus('Running')

      const loadSummary = async (runId: string) => {
        try {
          const run = await runsApi.get(runId)
          setRunResult(run)
        } catch {
          setRunResult({
            run_id: runId,
            flow_id: flowId,
            trigger_type: 'manual',
            status: result.status === 'success' ? 'success' : 'failed',
            started_at: new Date().toISOString(),
            ended_at: new Date().toISOString(),
            rows_processed: result.rows_processed ?? 0,
            rows_failed: 0,
            rows_written: 0,
            steps: [],
            error_message: result.error_message,
            triggered_by: '',
          })
        }
      }

      const cleanup = subscribeToRun(
        result.run_id,
        (event) => applyFlowEvent(event),
        () => {
          setRunning(false)
          cleanup()
          void loadSummary(result.run_id)
          setStatus('Done — see results below')
          setTimeout(() => setStatus(''), 4000)
        },
      )
    } catch (err) {
      setStatus('Run failed')
      setRunning(false)
    }
  }, [
    flowId,
    flowName,
    nodes,
    edges,
    isRunning,
    setRunning,
    setRunId,
    setRunResult,
    setRunPanelOpen,
    applyFlowEvent,
    resetRunState,
  ])

  const handleValidate = useCallback(async () => {
    setStatus('Validating…')
    setValidationPanelOpen(false)
    try {
      const definition = buildFlowDefinition(flowId, flowName, nodes, edges)
      await flowsApi.update(flowId, definition)
      const result = await flowsApi.validate(flowId)
      setValidation(result)
      setValidationPanelOpen(true)
      if (result.valid) {
        const n = result.warnings?.length ?? 0
        setStatus(n ? `Valid — ${n} warning${n === 1 ? '' : 's'} (see panel below)` : 'Valid ✓')
      } else {
        setStatus('Invalid — see details below')
      }
      if (result.valid && !result.warnings?.length) {
        setTimeout(() => setStatus(''), 3000)
      }
    } catch {
      setStatus('Validation error')
      setValidation({ valid: false, error: 'Could not reach the API. Check that the backend is running.' })
      setValidationPanelOpen(true)
    }
  }, [flowId, flowName, nodes, edges])

  const handleDeploy = useCallback(async () => {
    setDeploying(true)
    setStatus('Deploying…')
    setValidationPanelOpen(false)
    try {
      const definition = buildFlowDefinition(flowId, flowName, nodes, edges)
      await flowsApi.update(flowId, definition)
      markClean()
      const result = await flowsApi.deploy(flowId)
      setFlowStatus(result.status)
      setStatus('Deployed ✓')
      setValidation({ valid: true, warnings: [] })
      setTimeout(() => setStatus(''), 3000)
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as Error).message)
          : 'Deploy failed'
      setStatus('Deploy failed')
      setValidation({ valid: false, error: msg })
      setValidationPanelOpen(true)
    } finally {
      setDeploying(false)
    }
  }, [flowId, flowName, nodes, edges, markClean])

  const hasValidationDetails =
    validation &&
    (!validation.valid || (validation.warnings && validation.warnings.length > 0))

  const showValidationPanel = validationPanelOpen && hasValidationDetails

  return (
    <div className="toolbar-wrap">
    <div className="toolbar">
      <div className="toolbar__left">
        <span className="toolbar__flow-name">{flowName}</span>
        {flowStatus === 'deployed' && (
          <span className="toolbar__deployed-pill">deployed</span>
        )}
        {isDirty && <span className="toolbar__dirty">●</span>}
      </div>

      <div className="toolbar__center">
        {status && <span className="toolbar__status">{status}</span>}
        {validation?.valid && validation.warnings?.length && !validationPanelOpen ? (
          <button
            type="button"
            className="toolbar__warnings-link"
            onClick={() => setValidationPanelOpen(true)}
          >
            Show {validation.warnings.length} warning{validation.warnings.length === 1 ? '' : 's'}
          </button>
        ) : null}
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
          className="toolbar__btn toolbar__btn--deploy"
          onClick={handleDeploy}
          disabled={deploying || nodes.length === 0}
          title="Save, validate, and mark flow as deployed"
        >
          {deploying ? 'Deploying…' : 'Deploy'}
        </button>
        <button
          type="button"
          className="toolbar__btn toolbar__btn--ghost"
          onClick={() => setShowDockerCompose(true)}
          disabled={nodes.length === 0}
          title="Generate docker-compose for this flow only"
        >
          Docker
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

    {showDockerCompose && (
      <FlowDockerComposeModal
        flowId={flowId}
        flowName={flowName}
        nodes={nodes}
        edges={edges}
        onClose={() => setShowDockerCompose(false)}
      />
    )}

    {showValidationPanel && (
      <div
        className={clsx('toolbar-validation', {
          'toolbar-validation--error': !validation.valid,
          'toolbar-validation--warn': validation.valid && (validation.warnings?.length ?? 0) > 0,
        })}
        role="status"
      >
        <div className="toolbar-validation__head">
          <span className="toolbar-validation__title">
            {validation.valid
              ? `Validation passed with ${validation.warnings!.length} warning${validation.warnings!.length === 1 ? '' : 's'}`
              : 'Validation failed'}
          </span>
          <button
            type="button"
            className="toolbar-validation__close"
            onClick={() => setValidationPanelOpen(false)}
            aria-label="Dismiss validation details"
          >
            ×
          </button>
        </div>
        {!validation.valid && validation.error && (
          <p className="toolbar-validation__error">{validation.error}</p>
        )}
        {validation.warnings && validation.warnings.length > 0 && (
          <ul className="toolbar-validation__list">
            {warningLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        )}
        {validation.valid && validation.warnings?.length ? (
          <p className="toolbar-validation__hint">
            Warnings do not block deploy or run; defaults will be applied as described above.
          </p>
        ) : null}
      </div>
    )}
    </div>
  )
}
