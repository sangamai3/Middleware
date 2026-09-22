import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import './TemplatesPage.css'

interface TemplateSummary {
  id: string
  name: string
  description: string
  category: string
  tags: string[]
  author: string
  version: string
  connections: Array<{ id: string; connector_id: string; label: string }>
  parameters: Array<{ name: string; label: string; description?: string; default?: string; required?: boolean }>
}

const CATEGORY_COLORS: Record<string, string> = {
  'data-sync': '#2563eb',
  'etl': '#7c3aed',
  'notifications': '#ca8a04',
  'api': '#059669',
  'reporting': '#dc2626',
}

export function TemplatesPage() {
  const navigate = useNavigate()
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [searchText, setSearchText] = useState('')
  const [selected, setSelected] = useState<TemplateSummary | null>(null)

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['templates', categoryFilter],
    queryFn: () =>
      api.get<TemplateSummary[]>(
        `/templates${categoryFilter ? `?category=${encodeURIComponent(categoryFilter)}` : ''}`
      ),
    retry: false,
  })

  const categories = [...new Set(templates.map((t: TemplateSummary) => t.category).filter(Boolean))]

  const filtered = templates.filter((t: TemplateSummary) =>
    !searchText ||
    t.name.toLowerCase().includes(searchText.toLowerCase()) ||
    t.description.toLowerCase().includes(searchText.toLowerCase()) ||
    t.tags.some(tag => tag.toLowerCase().includes(searchText.toLowerCase()))
  )

  return (
    <div className="templates">
      <div className="templates__header">
        <div>
          <h1 className="templates__title">Integration Templates</h1>
          <p className="templates__sub">Start a flow from a pre-built integration pattern.</p>
        </div>
      </div>

      <div className="templates__toolbar">
        <input
          className="templates__search"
          placeholder="Search templates…"
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
        />
        <div className="category-filter">
          <button
            className={`cat-btn${categoryFilter === '' ? ' cat-btn--active' : ''}`}
            onClick={() => setCategoryFilter('')}
          >All</button>
          {categories.map(cat => (
            <button
              key={cat}
              className={`cat-btn${categoryFilter === cat ? ' cat-btn--active' : ''}`}
              onClick={() => setCategoryFilter(categoryFilter === cat ? '' : cat)}
            >{cat}</button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="templates-loading">Loading templates…</div>
      ) : filtered.length === 0 ? (
        <div className="templates-empty">No templates found.</div>
      ) : (
        <div className="templates-grid">
          {filtered.map((t: TemplateSummary) => (
            <div key={t.id} className="template-card" onClick={() => setSelected(t)}>
              <div className="template-card__top">
                <div
                  className="template-card__category"
                  style={{ background: `${CATEGORY_COLORS[t.category] ?? '#6b7280'}20`, color: CATEGORY_COLORS[t.category] ?? '#6b7280' }}
                >
                  {t.category}
                </div>
                <span className="template-card__version">v{t.version}</span>
              </div>
              <div className="template-card__name">{t.name}</div>
              <p className="template-card__desc">{t.description}</p>
              <div className="template-card__tags">
                {t.tags.slice(0, 3).map(tag => (
                  <span key={tag} className="tag">{tag}</span>
                ))}
              </div>
              <div className="template-card__author">by {t.author}</div>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <InstantiateModal
          template={selected}
          onClose={() => setSelected(null)}
          onCreated={(flowId) => { setSelected(null); navigate(`/flows/${flowId}`) }}
        />
      )}
    </div>
  )
}

// ── Instantiate modal ─────────────────────────────────────────────────────────

function InstantiateModal({
  template,
  onClose,
  onCreated,
}: {
  template: TemplateSummary
  onClose: () => void
  onCreated: (flowId: string) => void
}) {
  const [name, setName] = useState(`${template.name} copy`)
  const [params, setParams] = useState<Record<string, string>>(() => {
    const defaults: Record<string, string> = {}
    for (const p of template.parameters) {
      if (p.default != null) defaults[p.name] = String(p.default)
    }
    return defaults
  })
  const [connIds, setConnIds] = useState<Record<string, string>>(() => {
    const defaults: Record<string, string> = {}
    for (const c of template.connections) defaults[c.id] = ''
    return defaults
  })

  const mutation = useMutation({
    mutationFn: () =>
      api.post<{ flow_definition: Record<string, unknown> }>(
        `/templates/${template.id}/instantiate`,
        { name, parameters: params, connection_ids: connIds }
      ),
    onSuccess: (result) => {
      const flowId = (result.flow_definition as any).flow_id || name.toLowerCase().replace(/\s+/g, '-')
      onCreated(flowId)
    },
  })

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal__head">
          <h2 className="modal__title">{template.name}</h2>
          <button className="modal__close" onClick={onClose}>×</button>
        </div>
        <p className="modal__desc">{template.description}</p>

        <div className="modal__section">
          <label className="modal__label">Flow name</label>
          <input
            className="modal__input"
            value={name}
            onChange={e => setName(e.target.value)}
          />
        </div>

        {template.connections.length > 0 && (
          <div className="modal__section">
            <div className="modal__label" style={{ marginBottom: 8 }}>Connections</div>
            {template.connections.map(c => (
              <div key={c.id} className="modal__field">
                <label className="modal__field-label">{c.label} ({c.connector_id})</label>
                <input
                  className="modal__input"
                  placeholder={`connection ID for ${c.id}`}
                  value={connIds[c.id] || ''}
                  onChange={e => setConnIds(prev => ({ ...prev, [c.id]: e.target.value }))}
                />
              </div>
            ))}
          </div>
        )}

        {template.parameters.length > 0 && (
          <div className="modal__section">
            <div className="modal__label" style={{ marginBottom: 8 }}>Parameters</div>
            {template.parameters.map(p => (
              <div key={p.name} className="modal__field">
                <label className="modal__field-label">
                  {p.label || p.name}
                  {p.required && <span className="modal__required"> *</span>}
                  {p.description && <span className="modal__field-desc"> — {p.description}</span>}
                </label>
                <input
                  className="modal__input"
                  placeholder={p.default != null ? String(p.default) : p.name}
                  value={params[p.name] || ''}
                  onChange={e => setParams(prev => ({ ...prev, [p.name]: e.target.value }))}
                />
              </div>
            ))}
          </div>
        )}

        {mutation.error && (
          <div className="modal__error">{(mutation.error as any).message}</div>
        )}

        <div className="modal__actions">
          <button className="modal__cancel" onClick={onClose}>Cancel</button>
          <button
            className="modal__submit"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !name.trim()}
          >
            {mutation.isPending ? 'Creating…' : 'Create flow'}
          </button>
        </div>
      </div>
    </div>
  )
}
