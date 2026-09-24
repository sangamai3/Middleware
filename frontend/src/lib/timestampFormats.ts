/** Presets map to Python strftime patterns used by the flow engine. */
export const TIMESTAMP_FORMAT_PRESETS: { label: string; value: string }[] = [
  { label: 'Compact — 20260923_074530', value: '%Y%m%d_%H%M%S' },
  { label: 'ISO-style — 2026-09-23_07-45-30', value: '%Y-%m-%d_%H-%M-%S' },
  { label: 'Date only — 20260923', value: '%Y%m%d' },
  { label: 'Dense — 20260923074530', value: '%Y%m%d%H%M%S' },
  { label: 'US date + time — 09-23-2026_074530', value: '%m-%d-%Y_%H%M%S' },
]

export const DEFAULT_TIMESTAMP_FORMAT = TIMESTAMP_FORMAT_PRESETS[0].value

const CUSTOM = '__custom__'

export function isKnownTimestampFormat(fmt: string): boolean {
  return TIMESTAMP_FORMAT_PRESETS.some((p) => p.value === fmt)
}

export function timestampSelectValue(fmt: string): string {
  if (!fmt.trim()) return CUSTOM
  return isKnownTimestampFormat(fmt) ? fmt : CUSTOM
}

export function previewTimestampFormat(fmt: string): string {
  const pattern = fmt.trim() || DEFAULT_TIMESTAMP_FORMAT
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return pattern
    .replace(/%Y/g, String(d.getFullYear()))
    .replace(/%m/g, pad(d.getMonth() + 1))
    .replace(/%d/g, pad(d.getDate()))
    .replace(/%H/g, pad(d.getHours()))
    .replace(/%M/g, pad(d.getMinutes()))
    .replace(/%S/g, pad(d.getSeconds()))
}

export { CUSTOM as TIMESTAMP_FORMAT_CUSTOM }
