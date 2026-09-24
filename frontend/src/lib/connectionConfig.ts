import type { JSONSchema } from '@/types'

/** Match backend normalize_config — form fields often send booleans as strings. */
export function normalizeConnectionConfig(
  config: Record<string, string | boolean | number>,
  schema?: JSONSchema,
): Record<string, string | boolean | number> {
  if (!schema?.properties) return { ...config }
  const out: Record<string, string | boolean | number> = { ...config }
  for (const [key, prop] of Object.entries(schema.properties)) {
    const val = out[key]
    if (val === undefined || val === null) continue
    const ptype = prop.type
    if (ptype === 'boolean' && typeof val === 'string') {
      const lowered = val.trim().toLowerCase()
      if (['true', '1', 'yes', 'on'].includes(lowered)) out[key] = true
      else if (['false', '0', 'no', 'off', ''].includes(lowered)) out[key] = false
    } else if (ptype === 'integer' && typeof val === 'string' && /^\d+$/.test(val.trim())) {
      out[key] = parseInt(val.trim(), 10)
    }
  }
  return out
}
