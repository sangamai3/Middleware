import { useCallback, useEffect, useState } from 'react'
import { flowsApi } from '@/api/flows'
import { buildFlowDefinition } from '@/lib/flowDefinition'
import type { CanvasNode } from '@/components/nodes/BaseNode'
import type { Edge } from '@xyflow/react'
import './FlowDockerComposeModal.css'

interface Props {
  flowId: string
  flowName: string
  nodes: CanvasNode[]
  edges: Edge[]
  onClose: () => void
}

export function FlowDockerComposeModal({ flowId, flowName, nodes, edges, onClose }: Props) {
  const [profile, setProfile] = useState<'minimal' | 'standard' | 'large'>('minimal')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [compose, setCompose] = useState('')
  const [envExample, setEnvExample] = useState('')
  const [manifest, setManifest] = useState<{
    connector_ids: string[]
    pip_extras: string[]
    service_name: string
  } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const definition = buildFlowDefinition(flowId, flowName, nodes, edges)
      const res = await flowsApi.dockerCompose(flowId, {
        definition,
        memory_profile: profile,
      })
      setCompose(res.compose_yaml)
      setEnvExample(res.env_example)
      setManifest(res.manifest)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate compose')
    } finally {
      setLoading(false)
    }
  }, [flowId, flowName, nodes, edges, profile])

  useEffect(() => {
    void load()
  }, [load])

  const copy = (text: string) => {
    void navigator.clipboard.writeText(text)
  }

  return (
    <div className="flow-compose-modal" role="dialog" aria-modal="true">
      <div className="flow-compose-modal__backdrop" onClick={onClose} />
      <div className="flow-compose-modal__panel">
        <header className="flow-compose-modal__head">
          <div>
            <h2>Docker Compose (per-flow runtime)</h2>
            <p>Generated from connectors and steps in this flow.</p>
          </div>
          <button type="button" className="flow-compose-modal__close" onClick={onClose}>×</button>
        </header>

        <div className="flow-compose-modal__profiles">
          {(['minimal', 'standard', 'large'] as const).map((p) => (
            <button
              key={p}
              type="button"
              className={`flow-compose-modal__chip${profile === p ? ' flow-compose-modal__chip--on' : ''}`}
              onClick={() => setProfile(p)}
            >
              {p === 'minimal' ? 'Minimal RAM (192M)' : p === 'standard' ? 'Standard (512M)' : 'Large (1.5G)'}
            </button>
          ))}
        </div>

        {manifest && (
          <div className="flow-compose-modal__meta">
            <span>Connectors: <strong>{manifest.connector_ids.join(', ') || 'none'}</strong></span>
            {manifest.pip_extras.length > 0 && (
              <span>Pip extras: <strong>{manifest.pip_extras.join(', ')}</strong></span>
            )}
            <span>Service: <code>{manifest.service_name}</code></span>
          </div>
        )}

        {loading && <div className="flow-compose-modal__loading">Generating…</div>}
        {error && <div className="flow-compose-modal__error">{error}</div>}

        {!loading && !error && (
          <>
            <label className="flow-compose-modal__label">docker-compose.yml</label>
            <textarea className="flow-compose-modal__code" readOnly value={compose} rows={16} />
            <div className="flow-compose-modal__actions">
              <button type="button" className="btn btn--secondary" onClick={() => copy(compose)}>
                Copy compose
              </button>
              <button type="button" className="btn btn--ghost" onClick={() => copy(envExample)}>
                Copy .env example
              </button>
            </div>
            <p className="flow-compose-modal__hint">
              Create network once: <code>docker network create sangam-internal</code>.
              Build uses <code>Dockerfile.flow-worker</code> with only the pip extras required by this flow.
            </p>
          </>
        )}
      </div>
    </div>
  )
}
