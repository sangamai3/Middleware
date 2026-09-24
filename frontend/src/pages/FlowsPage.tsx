import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { flowsApi } from '@/api/flows'
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
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>('all')
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')

  const { data: flows = [], isLoading } = useQuery({
    queryKey: ['flows'],
    queryFn: () => flowsApi.list(),
  })

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
    onSuccess: () => qc.invalidateQueries({ queryKey: ['flows'] }),
  })

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
          <button type="button" className="btn btn--primary" onClick={() => setShowCreate(true)}>
            New flow
          </button>
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
                  <th>Created</th>
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
                    <td className="flows-table__date">{fmtDate(f.created_at)}</td>
                    <td className="flows-table__date">{fmtDate(f.updated_at)}</td>
                    <td className="flows-table__actions-col" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="flows-table__delete"
                        title="Delete flow"
                        onClick={() => {
                          if (confirm(`Delete "${f.name}"? This cannot be undone.`)) {
                            deleteMutation.mutate(f.flow_id)
                          }
                        }}
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
    </div>
  )
}
