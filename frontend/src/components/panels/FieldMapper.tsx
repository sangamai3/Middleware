import { useState, useCallback, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useMutation } from '@tanstack/react-query'
import { schemaApi, type SchemaField } from '@/api/schema'
import { aiApi, type AiMappingSuggestion } from '@/api/ai'
import { ApiError } from '@/api/client'
import type { CanvasNodeData } from '@/types'
import './FieldMapper.css'

type InferFn = (sample: string) => Promise<void>

// ─── Types ────────────────────────────────────────────────────────────────────

export interface MappingRule {
  id: string
  source: string
  target: string
  fn: string | null
  args: Record<string, string>
}

interface Props {
  data: CanvasNodeData
  onUpdate: (patch: Partial<CanvasNodeData>) => void
  previewColumns?: { name: string; data_type: string }[]
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TRANSFORM_FNS: { value: string; label: string; args?: { key: string; placeholder: string }[] }[] = [
  { value: '', label: '— none (pass-through)' },
  { value: 'upper', label: 'upper()' },
  { value: 'lower', label: 'lower()' },
  { value: 'strip', label: 'strip whitespace' },
  { value: 'to_str', label: 'to_str()' },
  { value: 'to_int', label: 'to_int()' },
  { value: 'to_float', label: 'to_float()' },
  { value: 'to_bool', label: 'to_bool()' },
  { value: 'to_datetime', label: 'parse_date()', args: [{ key: 'format', placeholder: '%Y-%m-%d' }] },
  { value: 'date_format', label: 'format_date()', args: [{ key: 'format', placeholder: '%d/%m/%Y' }] },
  { value: 'split', label: 'split(sep, i)', args: [{ key: 'sep', placeholder: ',' }, { key: 'index', placeholder: '0' }] },
  { value: 'substring', label: 'substring(s,e)', args: [{ key: 'start', placeholder: '0' }, { key: 'end', placeholder: '5' }] },
  { value: 'replace', label: 'replace(old,new)', args: [{ key: 'old', placeholder: 'foo' }, { key: 'new', placeholder: 'bar' }] },
  { value: 'if_null', label: 'if_null(default)', args: [{ key: 'default', placeholder: 'N/A' }] },
  { value: 'round', label: 'round(n)', args: [{ key: 'decimals', placeholder: '2' }] },
  { value: 'hash', label: 'hash()' },
  { value: 'json_extract', label: 'json_extract(key)', args: [{ key: 'key', placeholder: 'field_name' }] },
]

const TYPE_BADGE: Record<string, string> = {
  string: 'str', integer: 'int', number: 'num',
  boolean: 'bool', date: 'date', datetime: 'dt',
}

const TYPE_COLOR: Record<string, string> = {
  string: '#3b82f6', integer: '#10b981', number: '#10b981',
  boolean: '#f59e0b', date: '#8b5cf6', datetime: '#8b5cf6',
}

function uid() { return Math.random().toString(36).slice(2, 9) }

function dtypeToType(dtype: string): SchemaField['type'] {
  if (dtype.startsWith('int') || dtype === 'Int64') return 'integer'
  if (dtype.startsWith('float') || dtype.startsWith('decimal')) return 'number'
  if (dtype === 'bool') return 'boolean'
  if (dtype.includes('datetime') || dtype.includes('date')) return 'date'
  return 'string'
}

// ─── Generated YAML ───────────────────────────────────────────────────────────

function buildYaml(mappings: MappingRule[], dropUnmapped: boolean): string {
  if (!mappings.length) return '# No mapping rules yet'
  const lines: string[] = ['mappings:']
  for (const m of mappings) {
    if (!m.source) continue
    lines.push(`  - source: ${m.source}`)
    if (m.target && m.target !== m.source) lines.push(`    target: ${m.target}`)
    if (m.fn) lines.push(`    fn: ${m.fn}`)
    for (const [k, v] of Object.entries(m.args)) {
      if (v) lines.push(`    ${k}: ${v}`)
    }
  }
  lines.push(`drop_unmapped: ${dropUnmapped}`)
  return lines.join('\n')
}

// ─── SchemaPanel (source or target, with drag/drop support) ───────────────────

function SchemaPanel({
  label,
  role,
  fields,
  onChange,
  onInfer,
  placeholder,
  mappedFields,
  draggingField,
  onDragStart,
  onDragEnd,
  onDrop,
}: {
  label: string
  role: 'source' | 'target'
  fields: SchemaField[]
  onChange: (fields: SchemaField[]) => void
  onInfer?: InferFn
  placeholder?: string
  mappedFields: Set<string>
  draggingField: string | null
  onDragStart?: (name: string) => void
  onDragEnd?: () => void
  onDrop?: (targetField: string, sourceField: string) => void
}) {
  const [showSample, setShowSample] = useState(false)
  const [sample, setSample] = useState('')
  const [inferring, setInferring] = useState(false)
  const [inferError, setInferError] = useState<string | null>(null)
  const [dropOver, setDropOver] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const addField = () =>
    onChange([...fields, { name: '', type: 'string', nullable: false, date_format: null }])

  const updateField = (i: number, patch: Partial<SchemaField>) =>
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)))

  const removeField = (i: number) =>
    onChange(fields.filter((_, idx) => idx !== i))

  const runInfer = async (content: string) => {
    if (!onInfer) return
    setInferring(true)
    setInferError(null)
    try {
      await onInfer(content)
      setShowSample(false)
      setSample('')
    } catch (e) {
      setInferError(e instanceof Error ? e.message : 'Inference failed')
    } finally {
      setInferring(false)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try { await runInfer(await file.text()) }
    catch { setInferError('Could not read file') }
  }

  const isDropActive = role === 'target' && draggingField !== null

  return (
    <div className={`fm-schema${isDropActive ? ' fm-schema--drop-active' : ''}`}>
      <div className="fm-schema__head">
        <span className="fm-schema__label">{label}</span>
        <div className="fm-schema__actions">
          <button type="button" className="fm-btn fm-btn--ghost" disabled={inferring}
            onClick={() => fileInputRef.current?.click()} title="Browse file">
            {inferring ? <span className="fm-spin">⟳</span> : '📂'} Browse
          </button>
          <input ref={fileInputRef} type="file" accept=".csv,.json,.xml,.txt"
            style={{ display: 'none' }} onChange={handleFileChange} />
          <button type="button" className="fm-btn fm-btn--ghost"
            onClick={() => setShowSample((s) => !s)}>
            {showSample ? 'Cancel' : '⚡ Paste'}
          </button>
          <button type="button" className="fm-btn fm-btn--ghost" onClick={addField}>+ Add</button>
        </div>
      </div>

      {showSample && (
        <div className="fm-sample-box">
          <textarea className="fm-sample-ta" placeholder={placeholder} value={sample}
            rows={4} onChange={(e) => setSample(e.target.value)} />
          {inferError && <div className="fm-error">{inferError}</div>}
          <button type="button" className="fm-btn fm-btn--accent"
            disabled={!sample.trim() || inferring} onClick={() => runInfer(sample)}>
            {inferring ? <span className="fm-spin">⟳</span> : '⚡'} Infer schema
          </button>
        </div>
      )}
      {!showSample && inferError && <div className="fm-error">{inferError}</div>}

      {fields.length === 0 && !showSample && (
        <div className="fm-schema__empty">
          {role === 'target' && isDropActive
            ? 'Drop source fields here to map them'
            : 'Browse a file or paste a sample to define fields.'}
        </div>
      )}

      <div className="fm-field-list">
        {fields.map((f, i) => {
          const isMapped = mappedFields.has(f.name)
          const isTarget = role === 'target'
          const isOver = dropOver === f.name

          return (
            <div
              key={i}
              className={[
                'fm-field-row',
                role === 'source' ? 'fm-field-row--src' : 'fm-field-row--tgt',
                isMapped ? 'fm-field-row--mapped' : '',
                isOver ? 'fm-field-row--drop-over' : '',
                isTarget && isDropActive ? 'fm-field-row--droppable' : '',
              ].filter(Boolean).join(' ')}
              draggable={role === 'source'}
              onDragStart={role === 'source' ? (e) => {
                e.dataTransfer.setData('text/plain', f.name)
                e.dataTransfer.effectAllowed = 'link'
                onDragStart?.(f.name)
              } : undefined}
              onDragEnd={role === 'source' ? () => onDragEnd?.() : undefined}
              onDragOver={isTarget ? (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'link'; setDropOver(f.name) } : undefined}
              onDragLeave={isTarget ? () => setDropOver(null) : undefined}
              onDrop={isTarget ? (e) => {
                e.preventDefault()
                const src = e.dataTransfer.getData('text/plain')
                setDropOver(null)
                if (src) onDrop?.(f.name, src)
              } : undefined}
            >
              {role === 'source' && (
                <span className="fm-drag-handle" title="Drag to a target field to map">⠿</span>
              )}

              {isMapped && (
                <span
                  className="fm-mapped-dot"
                  style={{ background: TYPE_COLOR[f.type] ?? 'var(--accent)' }}
                  title="Mapped"
                />
              )}

              <input className="fm-field-name" placeholder="field_name" value={f.name}
                onChange={(e) => updateField(i, { name: e.target.value })} />

              <select className="fm-field-type" value={f.type}
                onChange={(e) => updateField(i, { type: e.target.value as SchemaField['type'] })}>
                <option value="string">string</option>
                <option value="integer">integer</option>
                <option value="number">number</option>
                <option value="boolean">boolean</option>
                <option value="date">date</option>
                <option value="datetime">datetime</option>
              </select>

              <button type="button" className="fm-field-del" onClick={() => removeField(i)} title="Remove">×</button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Modal ────────────────────────────────────────────────────────────────────

interface ModalProps {
  stepName: string
  srcFields: SchemaField[]
  tgtFields: SchemaField[]
  mappings: MappingRule[]
  dropUnmapped: boolean
  aiError: string | null
  aiPending: boolean
  canSuggest: boolean
  updateSrc: (f: SchemaField[]) => void
  updateTgt: (f: SchemaField[]) => void
  updateMappings: (m: MappingRule[]) => void
  updateDrop: (d: boolean) => void
  onAiSuggest: () => void
  inferSrcFn: InferFn
  inferTgtFn: InferFn
  onClose: () => void
}

function FieldMapperModal({
  stepName, srcFields, tgtFields, mappings, dropUnmapped,
  aiError, aiPending, canSuggest,
  updateSrc, updateTgt, updateMappings, updateDrop,
  onAiSuggest, inferSrcFn, inferTgtFn, onClose,
}: ModalProps) {
  const [draggingField, setDraggingField] = useState<string | null>(null)
  const [showCode, setShowCode] = useState(false)
  const [copied, setCopied] = useState(false)

  const addMapping = () =>
    updateMappings([...mappings, { id: uid(), source: srcFields[0]?.name ?? '', target: '', fn: null, args: {} }])

  const updateMapping = (id: string, patch: Partial<MappingRule>) =>
    updateMappings(mappings.map((m) => (m.id === id ? { ...m, ...patch } : m)))

  const removeMapping = (id: string) =>
    updateMappings(mappings.filter((m) => m.id !== id))

  const handleDrop = (targetField: string, sourceField: string) => {
    // Don't duplicate if a rule with this exact pair already exists
    const exists = mappings.some((m) => m.source === sourceField && m.target === targetField)
    if (!exists) {
      updateMappings([...mappings, { id: uid(), source: sourceField, target: targetField, fn: null, args: {} }])
    }
    setDraggingField(null)
  }

  const mappedSrc = new Set(mappings.map((m) => m.source).filter(Boolean))
  const mappedTgt = new Set(mappings.map((m) => m.target).filter(Boolean))

  const fnDef = (fn: string | null) => TRANSFORM_FNS.find((f) => f.value === (fn ?? ''))
  const configured = mappings.filter((m) => m.source && m.target)

  const yaml = buildYaml(mappings, dropUnmapped)

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(yaml)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      // fallback: select the pre
    }
  }

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return createPortal(
    <div className="fm-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="fm-modal" role="dialog" aria-modal="true" aria-label="Field Mapper">

        {/* ── Header ── */}
        <div className="fm-modal__header">
          <div className="fm-modal__titles">
            <span className="fm-modal__title">Field Mapper</span>
            <span className="fm-modal__subtitle">{stepName}</span>
          </div>
          <div className="fm-modal__actions">
            {canSuggest && (
              <button type="button" className="fm-btn fm-btn--ai" onClick={onAiSuggest} disabled={aiPending}>
                {aiPending ? <span className="fm-spin">⟳</span> : '✦'} AI suggest
              </button>
            )}
            <button type="button" className="fm-btn fm-btn--accent" onClick={onClose}>✓ Done</button>
            <button type="button" className="fm-modal__close" onClick={onClose} title="Close (Esc)">×</button>
          </div>
        </div>

        {/* ── Body ── */}
        <div className="fm-modal__body">

          {/* Drag hint */}
          {srcFields.length > 0 && tgtFields.length > 0 && (
            <div className="fm-drag-hint">
              <span>⠿ Drag a source field onto a target field to create a mapping</span>
            </div>
          )}

          {/* Side-by-side schemas */}
          <div className="fm-modal__schemas">
            <SchemaPanel
              label="Source schema"
              role="source"
              fields={srcFields}
              onChange={updateSrc}
              onInfer={inferSrcFn}
              placeholder={'id,name,order_date,amount\n1001,Alice,2024-03-15,1250.50'}
              mappedFields={mappedSrc}
              draggingField={draggingField}
              onDragStart={(name) => setDraggingField(name)}
              onDragEnd={() => setDraggingField(null)}
            />
            <SchemaPanel
              label="Target schema"
              role="target"
              fields={tgtFields}
              onChange={updateTgt}
              onInfer={inferTgtFn}
              placeholder={'{"record_id":"","full_name":"","revenue":0}'}
              mappedFields={mappedTgt}
              draggingField={draggingField}
              onDrop={handleDrop}
            />
          </div>

          {/* Mapping rules table */}
          <div className="fm-section">
            <div className="fm-section__head">
              <span className="fm-section__label">
                Field mappings
                {configured.length > 0 && (
                  <span className="fm-section__count">{configured.length}</span>
                )}
              </span>
              <button type="button" className="fm-btn fm-btn--ghost" onClick={addMapping}>+ Add rule</button>
            </div>

            {aiError && <div className="fm-error">{aiError}</div>}

            {mappings.length === 0 ? (
              <div className="fm-empty">
                Drag a source field onto a target to map it, or click <b>+ Add rule</b>.
              </div>
            ) : (
              <>
                <div className="fm-mapping-header">
                  <span style={{ flex: 2 }}>Source field</span>
                  <span className="fm-mapping-header__arr" />
                  <span style={{ flex: 2 }}>Transform</span>
                  <span className="fm-mapping-header__arr" />
                  <span style={{ flex: 2 }}>Target field</span>
                  <span style={{ width: 32 }} />
                </div>

                <div className="fm-mapping-list">
                  {mappings.map((m) => {
                    const currentFn = fnDef(m.fn)
                    return (
                      <div key={m.id} className="fm-mapping-row fm-mapping-row--modal">
                        <div className="fm-mapping-fields">
                          <div style={{ flex: 2, minWidth: 0 }}>
                            {srcFields.length > 0 ? (
                              <select className="fm-select" value={m.source}
                                onChange={(e) => updateMapping(m.id, { source: e.target.value })}>
                                <option value="">— pick —</option>
                                {srcFields.map((f) => (
                                  <option key={f.name} value={f.name}>{f.name} ({TYPE_BADGE[f.type] ?? f.type})</option>
                                ))}
                              </select>
                            ) : (
                              <input className="fm-input" placeholder="source_field" value={m.source}
                                onChange={(e) => updateMapping(m.id, { source: e.target.value })} />
                            )}
                          </div>
                          <div className="fm-arrow">→</div>
                          <div style={{ flex: 2, minWidth: 0 }}>
                            <select className="fm-select" value={m.fn ?? ''}
                              onChange={(e) => updateMapping(m.id, { fn: e.target.value || null, args: {} })}>
                              {TRANSFORM_FNS.map((f) => (
                                <option key={f.value} value={f.value}>{f.label}</option>
                              ))}
                            </select>
                          </div>
                          <div className="fm-arrow">→</div>
                          <div style={{ flex: 2, minWidth: 0 }}>
                            {tgtFields.length > 0 ? (
                              <select className="fm-select" value={m.target}
                                onChange={(e) => updateMapping(m.id, { target: e.target.value })}>
                                <option value="">— pick —</option>
                                {tgtFields.map((f) => (
                                  <option key={f.name} value={f.name}>{f.name} ({TYPE_BADGE[f.type] ?? f.type})</option>
                                ))}
                              </select>
                            ) : (
                              <input className="fm-input" placeholder="target_field" value={m.target}
                                onChange={(e) => updateMapping(m.id, { target: e.target.value })} />
                            )}
                          </div>
                          <button type="button" className="fm-del"
                            onClick={() => removeMapping(m.id)} title="Remove">×</button>
                        </div>

                        {currentFn?.args && currentFn.args.length > 0 && (
                          <div className="fm-fn-args">
                            {currentFn.args.map((a) => (
                              <div key={a.key} className="fm-fn-arg">
                                <label className="fm-fn-arg__label">{a.key}</label>
                                <input className="fm-fn-arg__input" placeholder={a.placeholder}
                                  value={m.args[a.key] ?? ''}
                                  onChange={(e) => updateMapping(m.id, { args: { ...m.args, [a.key]: e.target.value } })} />
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>

                <label className="fm-toggle">
                  <input type="checkbox" checked={dropUnmapped} onChange={(e) => updateDrop(e.target.checked)} />
                  <span className="fm-toggle__label">Drop unmapped source columns</span>
                </label>
              </>
            )}
          </div>

          {/* Generated code panel */}
          <div className="fm-code-section">
            <button type="button" className="fm-code-toggle" onClick={() => setShowCode((s) => !s)}>
              <span className="fm-code-toggle__icon">{showCode ? '▾' : '▸'}</span>
              Generated YAML config
              {configured.length > 0 && <span className="fm-code-toggle__badge">{configured.length} rules</span>}
            </button>
            {showCode && (
              <div className="fm-code-body">
                <button type="button" className="fm-code-copy" onClick={copyCode}>
                  {copied ? '✓ Copied' : 'Copy'}
                </button>
                <pre className="fm-code-pre">{yaml}</pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

// ─── Compact card ─────────────────────────────────────────────────────────────

function CompactCard({ srcCount, tgtCount, mappings, onOpen }: {
  srcCount: number
  tgtCount: number
  mappings: MappingRule[]
  onOpen: () => void
}) {
  const configured = mappings.filter((m) => m.source && m.target)
  return (
    <div className="fm-compact">
      <div className="fm-compact__meta">
        {srcCount > 0
          ? <span className="fm-compact__badge fm-compact__badge--src">{srcCount} source field{srcCount !== 1 ? 's' : ''}</span>
          : <span className="fm-compact__badge fm-compact__badge--empty">No source schema</span>}
        <span className="fm-compact__meta-arrow">→</span>
        {tgtCount > 0
          ? <span className="fm-compact__badge fm-compact__badge--tgt">{tgtCount} target field{tgtCount !== 1 ? 's' : ''}</span>
          : <span className="fm-compact__badge fm-compact__badge--empty">No target schema</span>}
      </div>

      {configured.length > 0 ? (
        <div className="fm-compact__rules">
          {configured.slice(0, 4).map((m) => (
            <div key={m.id} className="fm-compact__rule">
              <code>{m.source}</code>
              {m.fn && <span className="fm-compact__fn">{m.fn}</span>}
              <span>→</span>
              <code>{m.target}</code>
            </div>
          ))}
          {configured.length > 4 && (
            <div className="fm-compact__more">+{configured.length - 4} more</div>
          )}
        </div>
      ) : (
        <div className="fm-compact__empty">No mappings configured yet.</div>
      )}

      <button type="button" className="fm-compact__open" onClick={onOpen}>
        Configure field mappings ↗
      </button>
    </div>
  )
}

// ─── Main export ──────────────────────────────────────────────────────────────

export function FieldMapper({ data, onUpdate, previewColumns }: Props) {
  const cfg = (data.config as Record<string, unknown>) ?? {}

  const initialSrc: SchemaField[] = (() => {
    const stored = cfg.source_schema as SchemaField[] | undefined
    if (stored?.length) return stored
    if (previewColumns?.length) {
      return previewColumns.map((c) => ({
        name: c.name, type: dtypeToType(c.data_type), nullable: false, date_format: null,
      }))
    }
    return []
  })()

  const [srcFields, setSrcFields] = useState<SchemaField[]>(initialSrc)
  const [tgtFields, setTgtFields] = useState<SchemaField[]>((cfg.target_schema as SchemaField[]) ?? [])
  const [mappings, setMappings] = useState<MappingRule[]>(
    ((cfg.mappings as MappingRule[]) ?? []).map((m) => ({ ...m, id: m.id ?? uid() })),
  )
  const [dropUnmapped, setDropUnmapped] = useState<boolean>((cfg.drop_unmapped as boolean) ?? true)
  const [aiError, setAiError] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  const persist = useCallback(
    (src: SchemaField[], tgt: SchemaField[], maps: MappingRule[], drop: boolean) => {
      onUpdate({
        config: {
          ...cfg,
          source_schema: src,
          target_schema: tgt,
          mappings: maps.map(({ id: _id, ...rest }) => rest),
          drop_unmapped: drop,
        },
      })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [cfg, onUpdate],
  )

  const updateSrc = (f: SchemaField[]) => { setSrcFields(f); persist(f, tgtFields, mappings, dropUnmapped) }
  const updateTgt = (f: SchemaField[]) => { setTgtFields(f); persist(srcFields, f, mappings, dropUnmapped) }
  const updateMappings = (m: MappingRule[]) => { setMappings(m); persist(srcFields, tgtFields, m, dropUnmapped) }
  const updateDrop = (d: boolean) => { setDropUnmapped(d); persist(srcFields, tgtFields, mappings, d) }

  const inferSrcFn: InferFn = useCallback(
    async (sample: string) => { const res = await schemaApi.infer({ sample, label: 'source' }); updateSrc(res.fields) },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [updateSrc],
  )
  const inferTgtFn: InferFn = useCallback(
    async (sample: string) => { const res = await schemaApi.infer({ sample, label: 'target' }); updateTgt(res.fields) },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [updateTgt],
  )

  const suggestMutation = useMutation({
    mutationFn: () => aiApi.suggestMapping({
      source_schema: srcFields.map((f) => ({ name: f.name, data_type: f.type })),
      target_schema: tgtFields.map((f) => ({ name: f.name, data_type: f.type })),
    }),
    onSuccess: (res) => {
      setAiError(null)
      const suggested: MappingRule[] = res.suggestions.map((s: AiMappingSuggestion) => ({
        id: uid(), source: s.source_field, target: s.target_field, fn: s.transform ?? null, args: {},
      }))
      updateMappings([...mappings, ...suggested])
    },
    onError: (e) => {
      setAiError(
        e instanceof ApiError && e.status === 422 ? 'AI API key not configured.'
          : e instanceof Error ? e.message : 'Suggestion failed',
      )
    },
  })

  return (
    <>
      <CompactCard
        srcCount={srcFields.length}
        tgtCount={tgtFields.length}
        mappings={mappings}
        onOpen={() => setModalOpen(true)}
      />
      {modalOpen && (
        <FieldMapperModal
          stepName={String(data.label ?? 'Map Fields')}
          srcFields={srcFields}
          tgtFields={tgtFields}
          mappings={mappings}
          dropUnmapped={dropUnmapped}
          aiError={aiError}
          aiPending={suggestMutation.isPending}
          canSuggest={srcFields.length > 0 && tgtFields.length > 0}
          updateSrc={updateSrc}
          updateTgt={updateTgt}
          updateMappings={updateMappings}
          updateDrop={updateDrop}
          onAiSuggest={() => suggestMutation.mutate()}
          inferSrcFn={inferSrcFn}
          inferTgtFn={inferTgtFn}
          onClose={() => setModalOpen(false)}
        />
      )}
    </>
  )
}
