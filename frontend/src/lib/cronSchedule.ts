/**
 * Visual schedule builder → cron (5- or 6-field) or interval_seconds.
 * Unix cron: minute hour dom month dow (dow 0=Sun … 6=Sat).
 * Six-field (seconds): second minute hour dom month dow — used when second ≠ 0.
 */

export type RecurringUnit = 'seconds' | 'minutes' | 'hours'

export type SchedulePattern =
  | 'recurring'
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'custom'

export interface CronScheduleState {
  pattern: SchedulePattern
  /** Repeat every N (recurring mode) */
  every: number
  unit: RecurringUnit
  /** 0–23 */
  hour: number
  /** 0–59 */
  minute: number
  /** 0–59 */
  second: number
  /** 1–31 for monthly */
  dayOfMonth: number
  /** Mon=1 … Sun=0 (unix dow) */
  weekDays: number[]
  customCron: string
}

export const WEEKDAY_OPTIONS: { value: number; label: string; short: string }[] = [
  { value: 1, label: 'Monday', short: 'Mon' },
  { value: 2, label: 'Tuesday', short: 'Tue' },
  { value: 3, label: 'Wednesday', short: 'Wed' },
  { value: 4, label: 'Thursday', short: 'Thu' },
  { value: 5, label: 'Friday', short: 'Fri' },
  { value: 6, label: 'Saturday', short: 'Sat' },
  { value: 0, label: 'Sunday', short: 'Sun' },
]

export function defaultCronScheduleState(): CronScheduleState {
  return {
    pattern: 'daily',
    every: 15,
    unit: 'minutes',
    hour: 9,
    minute: 0,
    second: 0,
    dayOfMonth: 1,
    weekDays: [1, 2, 3, 4, 5],
    customCron: '0 9 * * 1-5',
  }
}

export interface BuiltSchedule {
  cron_expr: string | null
  interval_seconds: number | null
  summary: string
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.floor(n)))
}

function formatTime(h: number, m: number, s: number): string {
  const pad = (x: number) => String(x).padStart(2, '0')
  return s > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(h)}:${pad(m)}`
}

function joinDow(days: number[]): string {
  const sorted = [...new Set(days)].sort((a, b) => a - b)
  if (sorted.length === 0) return '*'
  if (sorted.length === 7) return '*'
  const isContiguous =
    sorted.length > 1 &&
    sorted.every((d, i) => i === 0 || d === sorted[i - 1] + 1 || (sorted[i - 1] === 6 && d === 0))
  if (isContiguous && sorted.length >= 2) {
    return `${sorted[0]}-${sorted[sorted.length - 1]}`
  }
  return sorted.join(',')
}

function cronFields(
  second: number,
  minute: number,
  hour: number,
  dom: string,
  month: string,
  dow: string,
): string {
  const s = clamp(second, 0, 59)
  const m = clamp(minute, 0, 59)
  const h = clamp(hour, 0, 23)
  if (s === 0) {
    return `${m} ${h} ${dom} ${month} ${dow}`
  }
  return `${s} ${m} ${h} ${dom} ${month} ${dow}`
}

export function buildScheduleFromState(state: CronScheduleState): BuiltSchedule {
  const every = clamp(state.every, 1, 9999)
  const h = clamp(state.hour, 0, 23)
  const m = clamp(state.minute, 0, 59)
  const s = clamp(state.second, 0, 59)
  const dom = clamp(state.dayOfMonth, 1, 31)

  switch (state.pattern) {
    case 'recurring': {
      if (state.unit === 'seconds') {
        return {
          cron_expr: null,
          interval_seconds: every,
          summary: `Every ${every} second${every === 1 ? '' : 's'}`,
        }
      }
      if (state.unit === 'minutes') {
        const expr = every === 60 ? '0 * * * *' : `*/${every} * * * *`
        return {
          cron_expr: expr,
          interval_seconds: null,
          summary: every === 60 ? 'Every hour' : `Every ${every} minute${every === 1 ? '' : 's'}`,
        }
      }
      const expr = every === 24 ? '0 0 * * *' : `0 */${every} * * *`
      return {
        cron_expr: expr,
        interval_seconds: null,
        summary: every === 24 ? 'Daily at midnight' : `Every ${every} hour${every === 1 ? '' : 's'}`,
      }
    }
    case 'daily': {
      const expr = cronFields(s, m, h, '*', '*', '*')
      return {
        cron_expr: expr,
        interval_seconds: null,
        summary: `Daily at ${formatTime(h, m, s)}`,
      }
    }
    case 'weekly': {
      const dow = joinDow(state.weekDays)
      const expr = cronFields(s, m, h, '*', '*', dow)
      const dayLabels = WEEKDAY_OPTIONS.filter((d) => state.weekDays.includes(d.value)).map((d) => d.short)
      const daysText =
        dayLabels.length === 0
          ? 'no days selected'
          : dayLabels.length === 7
            ? 'every day'
            : dayLabels.join(', ')
      return {
        cron_expr: expr,
        interval_seconds: null,
        summary: `Weekly on ${daysText} at ${formatTime(h, m, s)}`,
      }
    }
    case 'monthly': {
      const expr = cronFields(s, m, h, String(dom), '*', '*')
      return {
        cron_expr: expr,
        interval_seconds: null,
        summary: `Monthly on day ${dom} at ${formatTime(h, m, s)}`,
      }
    }
    case 'custom': {
      const raw = state.customCron.trim()
      return {
        cron_expr: raw || null,
        interval_seconds: null,
        summary: raw ? `Custom: ${raw}` : 'Enter a cron expression',
      }
    }
    default:
      return { cron_expr: '0 9 * * *', interval_seconds: null, summary: 'Daily at 09:00' }
  }
}

/** Best-effort parse of stored cron/interval back into builder state. */
export function parseScheduleToState(
  cron_expr: string | null,
  interval_seconds: number | null,
): CronScheduleState {
  const base = defaultCronScheduleState()
  if (interval_seconds != null && interval_seconds > 0) {
    return {
      ...base,
      pattern: 'recurring',
      every: interval_seconds,
      unit: 'seconds',
    }
  }
  if (!cron_expr?.trim()) return base

  const parts = cron_expr.trim().split(/\s+/)
  if (parts.length === 6) {
    const [sec, min, hour, dom, , dow] = parts
    base.second = parseInt(sec, 10) || 0
    base.minute = parseInt(min, 10) || 0
    base.hour = parseInt(hour, 10) || 0
    if (dom !== '*') {
      base.pattern = 'monthly'
      base.dayOfMonth = parseInt(dom, 10) || 1
    } else if (dow !== '*') {
      base.pattern = 'weekly'
      base.weekDays = expandDowToken(dow)
    } else {
      base.pattern = 'daily'
    }
    return base
  }
  if (parts.length === 5) {
    const [min, hour, dom, , dow] = parts
    if (min.startsWith('*/')) {
      return { ...base, pattern: 'recurring', every: parseInt(min.slice(2), 10) || 15, unit: 'minutes' }
    }
    if (hour.startsWith('*/')) {
      return { ...base, pattern: 'recurring', every: parseInt(hour.slice(2), 10) || 1, unit: 'hours' }
    }
    base.minute = parseInt(min, 10) || 0
    base.hour = parseInt(hour, 10) || 0
    base.second = 0
    if (dom !== '*') {
      base.pattern = 'monthly'
      base.dayOfMonth = parseInt(dom, 10) || 1
    } else if (dow !== '*') {
      base.pattern = 'weekly'
      base.weekDays = expandDowToken(dow)
    } else {
      base.pattern = 'daily'
    }
    return base
  }
  return { ...base, pattern: 'custom', customCron: cron_expr }
}

function expandDowToken(token: string): number[] {
  const out: number[] = []
  for (const piece of token.split(',')) {
    if (piece.includes('-')) {
      const [a, b] = piece.split('-').map((x) => parseInt(x, 10))
      if (!Number.isNaN(a) && !Number.isNaN(b)) {
        for (let i = a; i <= b; i++) out.push(i)
      }
    } else {
      const n = parseInt(piece, 10)
      if (!Number.isNaN(n)) out.push(n)
    }
  }
  return out.length ? out : [1, 2, 3, 4, 5]
}
