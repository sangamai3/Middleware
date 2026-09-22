import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { flowsApi } from '@/api/flows'
import './FlowsPage.css'

function statusBadge(status: string) {
  const cls: Record<string, string> = {
    deployed: 'badge--pass', failed: 'badge--fail', draft: 'badge--muted', paused: 'badge--warn',
  }
  return `badge ${cls[status] || 'badge--muted'}`
}

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
    + ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

export function FlowsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')

  const { data: flows = [], isLoading } = useQuery({
    queryKey: ['flows'],
    queryFn: () => flowsApi.list(),
  })

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
    setCreating(false)
  }

  return (
    <div className="flows-page">
      <div className="flows-page__header">
        <h1 className="flows-page__title">Flows</h1>
        <button
          className="btn btn--primary"
          onClick={() => setCreating(true)}
        >
          + New flow
        </button>
      </div>

      {creating && (
        <div className="flows-page__create-row">
          <input
            autoFocus
            placeholder="Flow name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') setCreating(false) }}
          />
          <button className="btn btn--primary" onClick={handleCreate} disabled={!newName.trim()}>
            Create
          </button>
          <button className="btn btn--ghost" onClick={() => setCreating(false)}>
            Cancel
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="flows-page__empty">Loading…</div>
      ) : flows.length === 0 ? (
        <div className="flows-page__empty">
          No flows yet. Create one to get started.
        </div>
      ) : (
        <table className="flows-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Flow ID</th>
              <th>Status</th>
              <th>Created</th>
              <th>Last updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {flows.map((f) => (
              <tr key={f.flow_id} className="flows-table__row" onClick={() => navigate(`/flows/${f.flow_id}`)}>
                <td className="flows-table__name">{f.name}</td>
                <td className="flows-table__id">{f.flow_id}</td>
                <td><span className={statusBadge(f.status)}>{f.status}</span></td>
                <td className="flows-table__ts">{fmtDate(f.created_at)}</td>
                <td className="flows-table__ts">{fmtDate(f.updated_at)}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  <button
                    className="flows-table__delete"
                    onClick={() => {
                      if (confirm(`Delete "${f.name}"?`)) deleteMutation.mutate(f.flow_id)
                    }}
                    title="Delete"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
