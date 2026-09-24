import { useState } from 'react'
import { aiApi, type AiMappingSuggestion } from '@/api/ai'
import { ApiError } from '@/api/client'
import type { CanvasNodeData } from '@/types'
import './AiFieldMapper.css'

interface Props {
  data: CanvasNodeData
  onUpdate: (patch: Partial<CanvasNodeData>) => void
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = value >= 0.8 ? 'var(--pass)' : value >= 0.5 ? 'var(--warn)' : 'var(--text-muted)'
  return (
    <div className="afm-conf">
      <div className="afm-conf__bar" style={{ width: `${pct}%`, background: color }} />
      <span className="afm-conf__label" style={{ color }}>{pct}%</span>
    </div>
  )
}

export function AiFieldMapper({ data, onUpdate }: Props) {
  const cfg = data.config as Record<string, unknown>
  const mappings = (cfg.field_mappings as Record<string, string>) ?? {}

  const [sourceText, setSourceText] = useState('')
  const [targetText, setTargetText] = useState('')
  const [suggestions, setSuggestions] = useState<AiMappingSuggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [applied, setApplied] = useState<Set<string>>(new Set())

  const parseFields = (text: string) =>
    text
      .split(/[\n,]+/)
      .map((f) => f.trim())
      .filter(Boolean)

  const handleSuggest = async () => {
    const srcFields = parseFields(sourceText)
    const tgtFields = parseFields(targetText)
    if (!srcFields.length || !tgtFields.length) return
    setLoading(true)
    setError(null)
    setSuggestions([])
    setApplied(new Set())
    try {
      const res = await aiApi.suggestMapping({
        source_schema: srcFields.map((name) => ({ name })),
        target_schema: tgtFields.map((name) => ({ name })),
      })
      setSuggestions(res.suggestions)
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setError('AI API key not configured on the server.')
      } else {
        setError(e instanceof Error ? e.message : 'Suggestion failed')
      }
    } finally {
      setLoading(false)
    }
  }

  const applyMapping = (s: AiMappingSuggestion) => {
    const next = { ...mappings, [s.source_field]: s.target_field }
    onUpdate({ config: { ...cfg, field_mappings: next } })
    setApplied((prev) => new Set([...prev, s.source_field]))
  }

  const applyAll = () => {
    const next = { ...mappings }
    suggestions.forEach((s) => { next[s.source_field] = s.target_field })
    onUpdate({ config: { ...cfg, field_mappings: next } })
    setApplied(new Set(suggestions.map((s) => s.source_field)))
  }

  const hasApplied = Object.keys(mappings).length > 0

  return (
    <div className="afm">
      <div className="afm__heading">
        <span className="afm__icon">✦</span> AI Field Mapper
      </div>

      <div className="afm__inputs">
        <div className="afm__field">
          <label className="afm__label">Source fields</label>
          <textarea
            className="afm__textarea"
            placeholder={'id\nfirst_name\nlast_name\nemail'}
            value={sourceText}
            onChange={(e) => setSourceText(e.target.value)}
            rows={4}
          />
        </div>
        <div className="afm__field">
          <label className="afm__label">Target fields</label>
          <textarea
            className="afm__textarea"
            placeholder={'user_id\nname_first\nname_last\nemail_address'}
            value={targetText}
            onChange={(e) => setTargetText(e.target.value)}
            rows={4}
          />
        </div>
      </div>

      <button
        type="button"
        className="afm__suggest-btn"
        onClick={handleSuggest}
        disabled={loading || !parseFields(sourceText).length || !parseFields(targetText).length}
      >
        {loading ? <><span className="afm__spin">⟳</span> Suggesting…</> : '✦ Suggest mappings'}
      </button>

      {error && <div className="afm__error">{error}</div>}

      {suggestions.length > 0 && (
        <div className="afm__results">
          <div className="afm__results-head">
            <span>{suggestions.length} suggestions</span>
            <button type="button" className="afm__apply-all" onClick={applyAll}>
              Apply all
            </button>
          </div>
          {suggestions.map((s) => (
            <div key={s.source_field} className={`afm__row${applied.has(s.source_field) ? ' afm__row--applied' : ''}`}>
              <div className="afm__row-fields">
                <span className="afm__field-name">{s.source_field}</span>
                <span className="afm__arrow">→</span>
                <span className="afm__field-name">{s.target_field}</span>
              </div>
              <ConfidenceBar value={s.confidence} />
              {s.reason && <div className="afm__reason">{s.reason}</div>}
              {s.transform && (
                <div className="afm__transform">transform: <code>{s.transform}</code></div>
              )}
              <button
                type="button"
                className="afm__apply"
                onClick={() => applyMapping(s)}
                disabled={applied.has(s.source_field)}
              >
                {applied.has(s.source_field) ? '✓ Applied' : 'Apply'}
              </button>
            </div>
          ))}
        </div>
      )}

      {hasApplied && (
        <div className="afm__applied-summary">
          <div className="afm__applied-head">Applied mappings</div>
          {Object.entries(mappings).map(([src, tgt]) => (
            <div key={src} className="afm__applied-row">
              <span>{src}</span>
              <span className="afm__arrow">→</span>
              <span>{tgt}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
