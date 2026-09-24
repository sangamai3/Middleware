import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { flowsApi } from '@/api/flows'
import './CommandPalette.css'

interface PaletteItem {
  id: string
  label: string
  sub?: string
  icon: string
  action: () => void
  group: string
}

function useCommandPalette() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(o => !o)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return { open, setOpen }
}

export function CommandPalette() {
  const { open, setOpen } = useCommandPalette()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const { data: flows = [] } = useQuery({
    queryKey: ['flows'],
    queryFn: () => flowsApi.list(),
    enabled: open,
    staleTime: 10_000,
  })

  useEffect(() => {
    if (open) {
      setQuery('')
      setCursor(0)
      setTimeout(() => inputRef.current?.focus(), 30)
    }
  }, [open])

  const go = (path: string) => { setOpen(false); navigate(path) }

  const STATIC: PaletteItem[] = [
    { id: 'nav-dash',    label: 'Dashboard',      icon: '⊞',  group: 'Navigate', action: () => go('/dashboard') },
    { id: 'nav-flows',   label: 'Flows',           icon: '◈',  group: 'Navigate', action: () => go('/flows') },
    { id: 'nav-runs',    label: 'Runs',            icon: '▶',  group: 'Navigate', action: () => go('/runs') },
    { id: 'nav-conns',   label: 'Connections',     icon: '⇄',  group: 'Navigate', action: () => go('/connections') },
    { id: 'nav-sched',   label: 'Scheduler',       icon: '⏱',  group: 'Navigate', action: () => go('/scheduler') },
    { id: 'nav-logs',    label: 'Logs',            icon: '☰',  group: 'Navigate', action: () => go('/logs') },
    { id: 'nav-insights',label: 'Insights',        icon: '◎',  group: 'Navigate', action: () => go('/insights') },
    { id: 'nav-lineage', label: 'Data Lineage',    icon: '⊸',  group: 'Navigate', action: () => go('/lineage') },
    { id: 'nav-gw',      label: 'API Gateway',     icon: '⬡',  group: 'Navigate', action: () => go('/gateway') },
    { id: 'act-newflow', label: 'New flow…',       icon: '+',  group: 'Actions',  action: () => go('/flows?new=1') },
    { id: 'act-tmpl',    label: 'Browse templates',icon: '⊡',  group: 'Actions',  action: () => go('/templates') },
  ]

  const flowItems: PaletteItem[] = (flows as { flow_id: string; name: string; status: string }[]).map(f => ({
    id: `flow-${f.flow_id}`,
    label: f.name || f.flow_id,
    sub: `${f.status} · ${f.flow_id}`,
    icon: '◈',
    group: 'Flows',
    action: () => go(`/flows/${f.flow_id}`),
  }))

  const items = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return [...STATIC, ...flowItems.slice(0, 5)]
    const all = [...STATIC, ...flowItems]
    return all.filter(i =>
      i.label.toLowerCase().includes(q) ||
      i.sub?.toLowerCase().includes(q) ||
      i.group.toLowerCase().includes(q)
    )
  }, [query, flowItems])

  useEffect(() => { setCursor(0) }, [items.length])

  const grouped = useMemo(() => {
    const map = new Map<string, PaletteItem[]>()
    items.forEach(i => {
      if (!map.has(i.group)) map.set(i.group, [])
      map.get(i.group)!.push(i)
    })
    return map
  }, [items])

  const flat = items

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setCursor(c => Math.min(c + 1, flat.length - 1)) }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setCursor(c => Math.max(c - 1, 0)) }
    if (e.key === 'Enter' && flat[cursor]) { flat[cursor].action() }
    if (e.key === 'Escape') setOpen(false)
  }

  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${cursor}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [cursor])

  if (!open) return null

  return (
    <div className="cp-backdrop" onClick={() => setOpen(false)}>
      <div className="cp-panel" role="dialog" aria-label="Command palette" onClick={e => e.stopPropagation()}>
        <div className="cp-search">
          <span className="cp-search__icon">⌕</span>
          <input
            ref={inputRef}
            className="cp-search__input"
            placeholder="Go to page, search flows…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
            spellCheck={false}
            autoComplete="off"
          />
          <kbd className="cp-search__esc" onClick={() => setOpen(false)}>Esc</kbd>
        </div>

        <div ref={listRef} className="cp-list">
          {flat.length === 0 && (
            <div className="cp-empty">No results for "{query}"</div>
          )}
          {[...grouped.entries()].map(([group, groupItems]) => (
            <div key={group} className="cp-group">
              <div className="cp-group__label">{group}</div>
              {groupItems.map(item => {
                const idx = flat.indexOf(item)
                return (
                  <button
                    key={item.id}
                    data-idx={idx}
                    className={`cp-item${idx === cursor ? ' cp-item--active' : ''}`}
                    onClick={item.action}
                    onMouseEnter={() => setCursor(idx)}
                  >
                    <span className="cp-item__icon">{item.icon}</span>
                    <span className="cp-item__body">
                      <span className="cp-item__label">{item.label}</span>
                      {item.sub && <span className="cp-item__sub">{item.sub}</span>}
                    </span>
                    {idx === cursor && <span className="cp-item__enter">↵</span>}
                  </button>
                )
              })}
            </div>
          ))}
        </div>

        <div className="cp-footer">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>Esc Close</span>
          <span className="cp-footer__trigger">⌘K to reopen</span>
        </div>
      </div>
    </div>
  )
}
