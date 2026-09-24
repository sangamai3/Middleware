import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { flowsApi, runsApi } from '@/api/flows'
import { connectorsApi } from '@/api/connectors'
import { aiApi } from '@/api/ai'
import { useToast } from '@/components/ui/Toast'
import { ApiError } from '@/api/client'
import type { FlowDefinition } from '@/types'
import {
  EmptyPanel,
  FlowStatusBadge,
  PageHeader,
  SurfaceCard,
} from '@/components/ui/enterprise/PageChrome'
import '@/components/ui/enterprise/PageChrome.css'
import './FlowsPage.css'

type FlowRow = {
  flow_id: string
  name: string
  status: string
  created_at?: string | null
  updated_at?: string | null
}

type RunSummary = { run_id: string; flow_id: string; status: string; started_at: string }

function fmtRel(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return `${Math.floor(diff / 86_400_000)}d ago`
}

function LastRunBadge({ run }: { run?: RunSummary }) {
  if (!run) return <span className="flows-run-badge flows-run-badge--none">—</span>
  const cls = run.status === 'success' ? 'pass' : run.status === 'failed' ? 'fail' : 'warn'
  const label = run.status === 'success' ? '✓' : run.status === 'failed' ? '✕' : '⟳'
  return (
    <span className={`flows-run-badge flows-run-badge--${cls}`} title={`Last run ${fmtRel(run.started_at)}`}>
      {label} {fmtRel(run.started_at)}
    </span>
  )
}

function DeleteConfirmModal({
  name,
  onConfirm,
  onCancel,
  pending,
}: {
  name: string
  onConfirm: () => void
  onCancel: () => void
  pending: boolean
}) {
  return (
    <div className="flows-modal-backdrop" onClick={onCancel}>
      <div className="flows-modal" role="alertdialog" aria-modal="true" aria-labelledby="del-title" onClick={e => e.stopPropagation()}>
        <h2 id="del-title" className="flows-modal__title">Delete flow?</h2>
        <p className="flows-modal__body">
          <strong>"{name}"</strong> will be permanently deleted. This cannot be undone.
        </p>
        <div className="flows-modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onCancel}>Cancel</button>
          <button type="button" className="btn btn--danger" onClick={onConfirm} disabled={pending}>
            {pending ? 'Deleting…' : 'Delete flow'}
          </button>
        </div>
      </div>
    </div>
  )
}

function AiGenerateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: (flowId: string) => void
}) {
  const [description, setDescription] = useState('')
  const [provider, setProvider] = useState<'anthropic' | 'openai'>('anthropic')
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<{ yaml: string; def: Record<string, unknown> } | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const toast = useToast()

  const { data: connectors = [] } = useQuery({
    queryKey: ['connectors-list'],
    queryFn: () => connectorsApi.list(),
  })

  const handleGenerate = async () => {
    if (!description.trim()) return
    setGenerating(true)
    setError(null)
    setResult(null)
    try {
      const res = await aiApi.generateFlow({
        description: description.trim(),
        provider,
        available_connectors: connectors.map((c) => c.connector_id),
      })
      setResult({ yaml: res.flow_yaml, def: res.flow_definition })
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setError(`${provider.toUpperCase()}_API_KEY is not configured on the server. Ask your admin to set it in the backend environment.`)
      } else {
        setError(e instanceof Error ? e.message : 'Generation failed')
      }
    } finally {
      setGenerating(false)
    }
  }

  const handleCreate = async () => {
    if (!result?.def) return
    setCreating(true)
    try {
      const def = result.def as Record<string, unknown>
      const flowId = `flow_${Date.now()}`
      const created = await flowsApi.create({
        flow_id: flowId,
        name: (def.name as string) || 'AI Generated Flow',
        description: (def.description as string) || description,
        version: '1',
        status: 'draft',
        trigger: 'manual',
        trigger_config: {},
        steps: [],
        variables: {},
        tags: ['ai-generated'],
      } as Partial<FlowDefinition>)
      toast.success(`Created "${def.name || 'AI Generated Flow'}"`)
      onCreated(created.flow_id)
    } catch {
      toast.error('Failed to create flow')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="flows-modal-backdrop" onClick={onClose}>
      <div
        className="flows-modal flows-modal--ai"
        role="dialog"
        aria-modal="true"
        aria-label="Generate flow with AI"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flows-modal__title">
          <span className="flows-modal__ai-icon">✦</span> Generate flow with AI
        </div>

        <div className="flows-modal__ai-row">
          <div className="flows-modal__ai-provider">
            <label className="flows-modal__ai-label">Provider</label>
            <select
              className="flows-modal__ai-select"
              value={provider}
              onChange={(e) => setProvider(e.target.value as 'anthropic' | 'openai')}
              disabled={generating}
            >
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="openai">OpenAI (GPT)</option>
            </select>
          </div>
        </div>

        <label className="flows-modal__ai-label">Describe your integration</label>
        <textarea
          className="flows-modal__ai-textarea"
          placeholder="e.g. Read active contacts from Salesforce, filter by region = EMEA, and write to PostgreSQL contacts table"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={generating}
          rows={4}
          autoFocus
        />

        {error && <div className="flows-modal__ai-error">{error}</div>}

        {result && (
          <div className="flows-modal__ai-preview">
            <div className="flows-modal__ai-preview-label">
              Generated with {result.def?.name ? <strong>{result.def.name as string}</strong> : 'AI'}
              <span className="flows-modal__ai-model"> · {provider}</span>
            </div>
            <pre className="flows-modal__ai-yaml">{result.yaml}</pre>
          </div>
        )}

        <div className="flows-modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Cancel
          </button>
          {result ? (
            <button
              type="button"
              className="btn btn--primary"
              onClick={handleCreate}
              disabled={creating}
            >
              {creating ? 'Creating…' : 'Create flow →'}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn--primary flows-modal__ai-gen-btn"
              onClick={handleGenerate}
              disabled={generating || !description.trim()}
            >
              {generating ? (
                <><span className="flows-modal__ai-spin">⟳</span> Generating…</>
              ) : (
                '✦ Generate'
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

const STATUS_FILTERS = ['all', 'deployed', 'draft', 'paused', 'failed'] as const

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    + ' · '
    + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

export function FlowsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>('all')
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<FlowRow | null>(null)
  const [runningFlowId, setRunningFlowId] = useState<string | null>(null)
  const [cloningFlowId, setCloningFlowId] = useState<string | null>(null)
  const [showAiModal, setShowAiModal] = useState(false)
  const importRef = useRef<HTMLInputElement>(null)

  const { data: flows = [], isLoading } = useQuery({
    queryKey: ['flows'],
    queryFn: () => flowsApi.list(),
  })

  const { data: runs = [] } = useQuery({
    queryKey: ['runs'],
    queryFn: () => runsApi.list(),
    refetchInterval: 30_000,
  })

  const lastRunByFlow = useMemo(() => {
    const map = new Map<string, RunSummary>()
    ;(runs as RunSummary[]).forEach(r => {
      const existing = map.get(r.flow_id)
      if (!existing || new Date(r.started_at) > new Date(existing.started_at)) {
        map.set(r.flow_id, r)
      }
    })
    return map
  }, [runs])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (flows as FlowRow[]).filter((f) => {
      if (statusFilter !== 'all' && f.status !== statusFilter) return false
      if (!q) return true
      return (
        f.name?.toLowerCase().includes(q)
        || f.flow_id.toLowerCase().includes(q)
      )
    })
  }, [flows, search, statusFilter])

  const createMutation = useMutation({
    mutationFn: (name: string) =>
      flowsApi.create({
        flow_id: `flow_${Date.now()}`,
        name,
        description: '',
        version: '1',
        status: 'draft',
        trigger: 'manual',
        trigger_config: {},
        steps: [],
        variables: {},
        tags: [],
        created_by: '',
      }),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['flows'] })
      navigate(`/flows/${result.flow_id}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => flowsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['flows'] })
      setDeleteTarget(null)
      toast.success('Flow deleted')
    },
    onError: () => toast.error('Failed to delete flow'),
  })

  const handleQuickRun = async (e: React.MouseEvent, f: FlowRow) => {
    e.stopPropagation()
    setRunningFlowId(f.flow_id)
    try {
      await flowsApi.execute(f.flow_id)
      qc.invalidateQueries({ queryKey: ['runs'] })
      toast.success(`"${f.name}" started`)
    } catch {
      toast.error(`Could not start "${f.name}"`)
    } finally {
      setRunningFlowId(null)
    }
  }

  const handleClone = async (e: React.MouseEvent, f: FlowRow) => {
    e.stopPropagation()
    setCloningFlowId(f.flow_id)
    try {
      const def = await flowsApi.get(f.flow_id) as FlowDefinition
      const newId = `flow_${Date.now()}`
      await flowsApi.create({ ...def, flow_id: newId, name: `${f.name} (copy)`, status: 'draft' })
      qc.invalidateQueries({ queryKey: ['flows'] })
      toast.success(`Cloned "${f.name}"`)
    } catch {
      toast.error('Failed to clone flow')
    } finally {
      setCloningFlowId(null)
    }
  }

  const handleExport = async (e: React.MouseEvent, f: FlowRow) => {
    e.stopPropagation()
    try {
      const def = await flowsApi.get(f.flow_id)
      const blob = new Blob([JSON.stringify(def, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${f.flow_id}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Export failed')
    }
  }

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = async (ev) => {
      try {
        const def = JSON.parse(ev.target?.result as string) as FlowDefinition
        const newId = `flow_${Date.now()}`
        const result = await flowsApi.create({ ...def, flow_id: newId, name: `${def.name ?? 'Imported flow'}`, status: 'draft' })
        qc.invalidateQueries({ queryKey: ['flows'] })
        toast.success(`Imported as "${def.name ?? newId}"`)
        navigate(`/flows/${result.flow_id}`)
      } catch {
        toast.error('Import failed — invalid JSON')
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  const handleCreate = () => {
    if (!newName.trim()) return
    createMutation.mutate(newName.trim())
    setNewName('')
    setShowCreate(false)
  }

  const counts = useMemo(() => {
    const list = flows as FlowRow[]
    return {
      all: list.length,
      deployed: list.filter((f) => f.status === 'deployed').length,
      draft: list.filter((f) => f.status === 'draft').length,
      paused: list.filter((f) => f.status === 'paused').length,
      failed: list.filter((f) => f.status === 'failed').length,
    }
  }, [flows])

  return (
    <div className="page-shell ep-page flows-page">
      <PageHeader
        meta="Integration catalog"
        title="Flows"
        description="Versioned integration definitions. Design in the canvas, validate, deploy, and schedule."
        actions={
          <>
            <input ref={importRef} type="file" accept=".json" hidden onChange={handleImport} />
            <button type="button" className="btn btn--ghost" onClick={() => importRef.current?.click()}>
              Import JSON
            </button>
            <button type="button" className="btn btn--ghost flows-ai-btn" onClick={() => setShowAiModal(true)}>
              ✦ Generate with AI
            </button>
            <button type="button" className="btn btn--primary" onClick={() => setShowCreate(true)}>
              New flow
            </button>
          </>
        }
      />

      {showCreate && (
        <div className="flows-create-modal" role="dialog" aria-labelledby="flows-create-title">
          <div className="flows-create-modal__backdrop" onClick={() => setShowCreate(false)} />
          <div className="flows-create-modal__panel">
            <h2 id="flows-create-title" className="flows-create-modal__title">Create flow</h2>
            <p className="flows-create-modal__sub">You can add steps and connections in the designer.</p>
            <input
              autoFocus
              className="flows-create-modal__input"
              placeholder="e.g. CRM to warehouse sync"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreate()
                if (e.key === 'Escape') setShowCreate(false)
              }}
            />
            <div className="flows-create-modal__actions">
              <button type="button" className="btn btn--ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={handleCreate}
                disabled={!newName.trim() || createMutation.isPending}
              >
                {createMutation.isPending ? 'Creating…' : 'Open designer'}
              </button>
            </div>
          </div>
        </div>
      )}

      <SurfaceCard noPadding>
        <div className="flows-page__toolbar-wrap">
          <div className="ep-toolbar">
            <div className="ep-search">
              <span className="ep-search__icon" aria-hidden>⌕</span>
              <input
                type="search"
                placeholder="Search by name or ID…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Search flows"
              />
            </div>
            <div className="ep-chips" role="tablist" aria-label="Filter by status">
              {STATUS_FILTERS.map((s) => (
                <button
                  key={s}
                  type="button"
                  role="tab"
                  aria-selected={statusFilter === s}
                  className={`ep-chip${statusFilter === s ? ' ep-chip--on' : ''}`}
                  onClick={() => setStatusFilter(s)}
                >
                  {s === 'all' ? 'All' : s}
                  <span className="flows-page__chip-count">{counts[s]}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="flows-page__loading">Loading flows…</div>
        ) : filtered.length === 0 ? (
          <EmptyPanel
            icon="◇"
            title={search || statusFilter !== 'all' ? 'No matching flows' : 'No flows yet'}
            description={
              search || statusFilter !== 'all'
                ? 'Try a different search or clear filters.'
                : 'Start with a name — we will open the designer for you.'
            }
            action={
              !search && statusFilter === 'all' ? (
                <button type="button" className="btn btn--primary" onClick={() => setShowCreate(true)}>
                  New flow
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => { setSearch(''); setStatusFilter('all') }}
                >
                  Clear filters
                </button>
              )
            }
          />
        ) : (
          <div className="ep-table-wrap">
            <table className="ep-table flows-table">
              <thead>
                <tr>
                  <th>Flow</th>
                  <th>Status</th>
                  <th>Last run</th>
                  <th>Updated</th>
                  <th className="flows-table__actions-col" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((f) => (
                  <tr
                    key={f.flow_id}
                    className="ep-table__row"
                    onClick={() => navigate(`/flows/${f.flow_id}`)}
                  >
                    <td>
                      <div className="ep-table__primary">{f.name}</div>
                      <div className="ep-table__mono ep-table__secondary">{f.flow_id}</div>
                    </td>
                    <td><FlowStatusBadge status={f.status} /></td>
                    <td><LastRunBadge run={lastRunByFlow.get(f.flow_id)} /></td>
                    <td className="flows-table__date">{fmtDate(f.updated_at)}</td>
                    <td className="flows-table__actions-col" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="flows-table__run"
                        title="Run now"
                        disabled={runningFlowId === f.flow_id}
                        onClick={(e) => handleQuickRun(e, f)}
                      >
                        {runningFlowId === f.flow_id ? '⟳' : '▶'}
                      </button>
                      <button
                        type="button"
                        className="flows-table__action-btn"
                        title="Clone flow"
                        disabled={cloningFlowId === f.flow_id}
                        onClick={(e) => handleClone(e, f)}
                      >
                        {cloningFlowId === f.flow_id ? '⟳' : '⧉'}
                      </button>
                      <button
                        type="button"
                        className="flows-table__action-btn"
                        title="Export as JSON"
                        onClick={(e) => handleExport(e, f)}
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        className="flows-table__delete"
                        title="Delete flow"
                        onClick={() => setDeleteTarget(f)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {deleteTarget && (
        <DeleteConfirmModal
          name={deleteTarget.name}
          onConfirm={() => deleteMutation.mutate(deleteTarget.flow_id)}
          onCancel={() => setDeleteTarget(null)}
          pending={deleteMutation.isPending}
        />
      )}

      {showAiModal && (
        <AiGenerateModal
          onClose={() => setShowAiModal(false)}
          onCreated={(id) => {
            setShowAiModal(false)
            qc.invalidateQueries({ queryKey: ['flows'] })
            navigate(`/flows/${id}`)
          }}
        />
      )}
    </div>
  )
}
