import { useState, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { schemaApi, type SchemaField } from '@/api/schema'
import { aiApi, type AiMappingSuggestion } from '@/api/ai'
import { ApiError } from '@/api/client'
import type { CanvasNodeData } from '@/types'
import './FieldMapper.css'

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
  /** Pre-fetched columns from the Preview API (auto-populated) */
  previewColumns?: { name: string; data_type: string }[]
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TRANSFORM_FNS: { value: string; label: string; args?: { key: string; placeholder: string }[] }[] = [
  { value: '', label: '— none (pass-through)' },
  { value: 'upper', label: 'upper()' },
  { value: 'lower', label: 'lower()' },
  { value: 'strip', label: 'trim / strip whitespace' },
  { value: 'to_str', label: 'to_str() — cast to string' },
  { value: 'to_int', label: 'to_int() — cast to integer' },
  { value: 'to_float', label: 'to_float() — cast to decimal' },
  { value: 'to_bool', label: 'to_bool() — cast to boolean' },
  { value: 'to_datetime', label: 'parse_date()', args: [{ key: 'format', placeholder: '%Y-%m-%d' }] },
  { value: 'date_format', label: 'format_date()', args: [{ key: 'format', placeholder: '%d/%m/%Y' }] },
  { value: 'split', label: 'split(sep, index)', args: [{ key: 'sep', placeholder: ',' }, { key: 'index', placeholder: '0' }] },
  { value: 'substring', label: 'substring(start, end)', args: [{ key: 'start', placeholder: '0' }, { key: 'end', placeholder: '5' }] },
  { value: 'replace', label: 'replace(old, new)', args: [{ key: 'old', placeholder: 'foo' }, { key: 'new', placeholder: 'bar' }] },
  { value: 'if_null', label: 'if_null(default)', args: [{ key: 'default', placeholder: 'N/A' }] },
  { value: 'round', label: 'round(decimals)', args: [{ key: 'decimals', placeholder: '2' }] },
  { value: 'hash', label: 'hash() — SHA-like hash' },
  { value: 'json_extract', label: 'json_extract(key)', args: [{ key: 'key', placeholder: 'field_name' }] },
]

const TYPE_BADGE: Record<string, string> = {
  string: 'str', integer: 'int', number: 'num',
  boolean: 'bool', date: 'date', datetime: 'dt',
}

function uid() { return Math.random().toString(36).slice(2, 9) }

function dtypeToType(dtype: string): SchemaField['type'] {
  if (dtype.startsWith('int') || dtype === 'Int64') return 'integer'
  if (dtype.startsWith('float') || dtype.startsWith('decimal')) return 'number'
  if (dtype === 'bool') return 'boolean'
  if (dtype.includes('datetime') || dtype.includes('date')) return 'date'
  return 'string'
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SchemaEditor({
  label,
  fields,
  onChange,
  onInfer,
  inferring,
  placeholder,
  showInfer,
}: {
  label: string
  fields: SchemaField[]
  onChange: (fields: SchemaField[]) => void
  onInfer?: (sample: string) => void
  inferring?: boolean
  placeholder?: string
  showInfer?: boolean
}) {
  const [showSample, setShowSample] = useState(false)
  const [sample, setSample] = useState('')

  const addField = () =>
    onChange([...fields, { name: '', type: 'string', nullable: false, date_format: null }])

  const updateField = (i: number, patch: Partial<SchemaField>) =>
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)))

  const removeField = (i: number) =>
    onChange(fields.filter((_, idx) => idx !== i))

  return (
    <div className="fm-schema">
      <div className="fm-schema__head">
        <span className="fm-schema__label">{label}</span>
        <div className="fm-schema__actions">
          {showInfer && (
            <button
              type="button"
              className="fm-btn fm-btn--ghost"
              onClick={() => setShowSample((s) => !s)}
            >
              {showSample ? 'Cancel' : '⚡ From sample'}
            </button>
          )}
          <button type="button" className="fm-btn fm-btn--ghost" onClick={addField}>
            + Add field
          </button>
        </div>
      </div>

      {showSample && showInfer && (
        <div className="fm-sample-box">
          <textarea
            className="fm-sample-ta"
            placeholder={placeholder}
            value={sample}
            rows={4}
            onChange={(e) => setSample(e.target.value)}
          />
          <button
            type="button"
            className="fm-btn fm-btn--accent"
            disabled={!sample.trim() || inferring}
            onClick={() => {
              onInfer?.(sample)
              setShowSample(false)
              setSample('')
            }}
          >
            {inferring ? <span className="fm-spin">⟳</span> : '⚡'} Infer schema
          </button>
        </div>
      )}

      {fields.length === 0 && (
        <div className="fm-schema__empty">No fields defined — paste a sample or add manually.</div>
      )}

      <div className="fm-field-list">
        {fields.map((f, i) => (
          <div key={i} className="fm-field-row">
            <input
              className="fm-field-name"
              placeholder="field_name"
              value={f.name}
              onChange={(e) => updateField(i, { name: e.target.value })}
            />
            <select
              className="fm-field-type"
              value={f.type}
              onChange={(e) => updateField(i, { type: e.target.value as SchemaField['type'] })}
            >
              <option value="string">string</option>
              <option value="integer">integer</option>
              <option value="number">number</option>
              <option value="boolean">boolean</option>
              <option value="date">date</option>
              <option value="datetime">datetime</option>
            </select>
            <button
              type="button"
              className="fm-field-del"
              onClick={() => removeField(i)}
              title="Remove field"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function FieldMapper({ data, onUpdate, previewColumns }: Props) {
  const cfg = (data.config as Record<string, unknown>) ?? {}

  // Initialise source schema from preview columns if available and no schema yet
  const initialSrc: SchemaField[] = (() => {
    const stored = cfg.source_schema as SchemaField[] | undefined
    if (stored?.length) return stored
    if (previewColumns?.length) {
      return previewColumns.map((c) => ({
        name: c.name,
        type: dtypeToType(c.data_type),
        nullable: false,
        date_format: null,
      }))
    }
    return []
  })()

  const [srcFields, setSrcFields] = useState<SchemaField[]>(initialSrc)
  const [tgtFields, setTgtFields] = useState<SchemaField[]>(
    (cfg.target_schema as SchemaField[]) ?? [],
  )
  const [mappings, setMappings] = useState<MappingRule[]>(
    ((cfg.mappings as MappingRule[]) ?? []).map((m) => ({ ...m, id: m.id ?? uid() })),
  )
  const [dropUnmapped, setDropUnmapped] = useState<boolean>(
    (cfg.drop_unmapped as boolean) ?? true,
  )
  const [aiError, setAiError] = useState<string | null>(null)

  // ── Persist to node config on every change ──────────────────────────────
  const persist = useCallback(
    (
      src: SchemaField[],
      tgt: SchemaField[],
      maps: MappingRule[],
      drop: boolean,
    ) => {
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

  // ── Schema inference ────────────────────────────────────────────────────
  const inferSrc = useMutation({
    mutationFn: (sample: string) => schemaApi.infer({ sample, label: 'source' }),
    onSuccess: (res) => updateSrc(res.fields),
  })

  const inferTgt = useMutation({
    mutationFn: (sample: string) => schemaApi.infer({ sample, label: 'target' }),
    onSuccess: (res) => updateTgt(res.fields),
  })

  // ── AI suggestions ──────────────────────────────────────────────────────
  const suggestMutation = useMutation({
    mutationFn: () =>
      aiApi.suggestMapping({
        source_schema: srcFields.map((f) => ({ name: f.name, data_type: f.type })),
        target_schema: tgtFields.map((f) => ({ name: f.name, data_type: f.type })),
      }),
    onSuccess: (res) => {
      setAiError(null)
      const suggested: MappingRule[] = res.suggestions.map((s: AiMappingSuggestion) => ({
        id: uid(),
        source: s.source_field,
        target: s.target_field,
        fn: s.transform ?? null,
        args: {},
      }))
      updateMappings([...mappings, ...suggested])
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 422) {
        setAiError('AI API key not configured.')
      } else {
        setAiError(e instanceof Error ? e.message : 'Suggestion failed')
      }
    },
  })

  // ── Mapping CRUD ─────────────────────────────────────────────────────────
  const addMapping = () =>
    updateMappings([
      ...mappings,
      { id: uid(), source: srcFields[0]?.name ?? '', target: '', fn: null, args: {} },
    ])

  const updateMapping = (id: string, patch: Partial<MappingRule>) =>
    updateMappings(mappings.map((m) => (m.id === id ? { ...m, ...patch } : m)))

  const removeMapping = (id: string) =>
    updateMappings(mappings.filter((m) => m.id !== id))

  const fnDef = (fn: string | null) => TRANSFORM_FNS.find((f) => f.value === (fn ?? ''))

  const canSuggest = srcFields.length > 0 && tgtFields.length > 0

  return (
    <div className="fm">
      {/* Source schema */}
      <SchemaEditor
        label="Source schema"
        fields={srcFields}
        onChange={updateSrc}
        onInfer={(s) => inferSrc.mutate(s)}
        inferring={inferSrc.isPending}
        showInfer
        placeholder={'id,name,created_date,amount\n1001,Alice,2024-03-15,1250.50'}
      />

      {/* Target schema */}
      <SchemaEditor
        label="Target schema"
        fields={tgtFields}
        onChange={updateTgt}
        onInfer={(s) => inferTgt.mutate(s)}
        inferring={inferTgt.isPending}
        showInfer
        placeholder={'{"record_id":"","month":"","revenue":0}'}
      />

      {/* Mapping rules */}
      <div className="fm-section">
        <div className="fm-section__head">
          <span className="fm-section__label">Field mappings</span>
          <div style={{ display: 'flex', gap: 6 }}>
            {canSuggest && (
              <button
                type="button"
                className="fm-btn fm-btn--ai"
                onClick={() => suggestMutation.mutate()}
                disabled={suggestMutation.isPending}
              >
                {suggestMutation.isPending ? <span className="fm-spin">⟳</span> : '✦'} AI suggest
              </button>
            )}
            <button type="button" className="fm-btn fm-btn--ghost" onClick={addMapping}>
              + Add rule
            </button>
          </div>
        </div>

        {aiError && <div className="fm-error">{aiError}</div>}

        {mappings.length === 0 && (
          <div className="fm-empty">
            No mapping rules yet. Add rules manually or click <b>✦ AI suggest</b>.
          </div>
        )}

        <div className="fm-mapping-list">
          {mappings.map((m) => {
            const currentFn = fnDef(m.fn)
            return (
              <div key={m.id} className="fm-mapping-row">
                <div className="fm-mapping-fields">
                  {/* Source field selector */}
                  <div className="fm-mapping-col">
                    <label className="fm-col-label">Source</label>
                    {srcFields.length > 0 ? (
                      <select
                        className="fm-select"
                        value={m.source}
                        onChange={(e) => updateMapping(m.id, { source: e.target.value })}
                      >
                        <option value="">— pick field —</option>
                        {srcFields.map((f) => (
                          <option key={f.name} value={f.name}>
                            {f.name} ({TYPE_BADGE[f.type] ?? f.type})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="fm-input"
                        placeholder="source_field"
                        value={m.source}
                        onChange={(e) => updateMapping(m.id, { source: e.target.value })}
                      />
                    )}
                  </div>

                  <div className="fm-arrow">→</div>

                  {/* Transform picker */}
                  <div className="fm-mapping-col">
                    <label className="fm-col-label">Transform</label>
                    <select
                      className="fm-select"
                      value={m.fn ?? ''}
                      onChange={(e) =>
                        updateMapping(m.id, { fn: e.target.value || null, args: {} })
                      }
                    >
                      {TRANSFORM_FNS.map((f) => (
                        <option key={f.value} value={f.value}>
                          {f.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="fm-arrow">→</div>

                  {/* Target field */}
                  <div className="fm-mapping-col">
                    <label className="fm-col-label">Target</label>
                    {tgtFields.length > 0 ? (
                      <select
                        className="fm-select"
                        value={m.target}
                        onChange={(e) => updateMapping(m.id, { target: e.target.value })}
                      >
                        <option value="">— pick field —</option>
                        {tgtFields.map((f) => (
                          <option key={f.name} value={f.name}>
                            {f.name} ({TYPE_BADGE[f.type] ?? f.type})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="fm-input"
                        placeholder="target_field"
                        value={m.target}
                        onChange={(e) => updateMapping(m.id, { target: e.target.value })}
                      />
                    )}
                  </div>

                  <button
                    type="button"
                    className="fm-del"
                    onClick={() => removeMapping(m.id)}
                    title="Remove rule"
                  >
                    ×
                  </button>
                </div>

                {/* Transform args (shown only when the fn needs params) */}
                {currentFn?.args && currentFn.args.length > 0 && (
                  <div className="fm-fn-args">
                    {currentFn.args.map((a) => (
                      <div key={a.key} className="fm-fn-arg">
                        <label className="fm-fn-arg__label">{a.key}</label>
                        <input
                          className="fm-fn-arg__input"
                          placeholder={a.placeholder}
                          value={m.args[a.key] ?? ''}
                          onChange={(e) =>
                            updateMapping(m.id, {
                              args: { ...m.args, [a.key]: e.target.value },
                            })
                          }
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Drop unmapped toggle */}
        {mappings.length > 0 && (
          <label className="fm-toggle">
            <input
              type="checkbox"
              checked={dropUnmapped}
              onChange={(e) => updateDrop(e.target.checked)}
            />
            <span className="fm-toggle__label">
              Only write mapped fields (drop unmapped source columns)
            </span>
          </label>
        )}
      </div>

      {/* Summary */}
      {mappings.filter((m) => m.source && m.target).length > 0 && (
        <div className="fm-summary">
          <div className="fm-summary__head">
            {mappings.filter((m) => m.source && m.target).length} mapping rule
            {mappings.filter((m) => m.source && m.target).length !== 1 ? 's' : ''} configured
          </div>
          {mappings
            .filter((m) => m.source && m.target)
            .map((m) => (
              <div key={m.id} className="fm-summary__row">
                <code>{m.source}</code>
                {m.fn && <span className="fm-summary__fn">{m.fn}</span>}
                <span className="fm-summary__arr">→</span>
                <code>{m.target}</code>
              </div>
            ))}
        </div>
      )}
    </div>
  )
}
