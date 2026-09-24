import {
  buildScheduleFromState,
  type CronScheduleState,
  type SchedulePattern,
  WEEKDAY_OPTIONS,
} from '@/lib/cronSchedule'
import './CronScheduleBuilder.css'

const PATTERNS: { id: SchedulePattern; label: string }[] = [
  { id: 'recurring', label: 'Every…' },
  { id: 'daily', label: 'Daily' },
  { id: 'weekly', label: 'Weekly' },
  { id: 'monthly', label: 'Monthly' },
  { id: 'custom', label: 'Advanced' },
]

export interface CronScheduleBuilderProps {
  value: CronScheduleState
  onChange: (next: CronScheduleState) => void
}

export function CronScheduleBuilder({ value, onChange }: CronScheduleBuilderProps) {
  const built = buildScheduleFromState(value)

  const set = (patch: Partial<CronScheduleState>) => onChange({ ...value, ...patch })

  const toggleWeekDay = (dow: number) => {
    const has = value.weekDays.includes(dow)
    const next = has ? value.weekDays.filter((d) => d !== dow) : [...value.weekDays, dow]
    set({ weekDays: next.length ? next : [dow] })
  }

  return (
    <div className="cron-builder">
      <div className="cron-builder__patterns">
        {PATTERNS.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`cron-builder__pattern${value.pattern === p.id ? ' cron-builder__pattern--active' : ''}`}
            onClick={() => set({ pattern: p.id })}
          >
            {p.label}
          </button>
        ))}
      </div>

      {value.pattern === 'recurring' && (
        <div className="cron-builder__row cron-builder__row--inline">
          <label>Repeat every</label>
          <input
            type="number"
            className="cron-builder__num"
            min={1}
            max={9999}
            value={value.every}
            onChange={(e) => set({ every: parseInt(e.target.value, 10) || 1 })}
          />
          <select
            className="cron-builder__select"
            value={value.unit}
            onChange={(e) => set({ unit: e.target.value as CronScheduleState['unit'] })}
          >
            <option value="seconds">seconds</option>
            <option value="minutes">minutes</option>
            <option value="hours">hours</option>
          </select>
        </div>
      )}

      {(value.pattern === 'daily' || value.pattern === 'weekly' || value.pattern === 'monthly') && (
        <>
          {value.pattern === 'monthly' && (
            <div className="cron-builder__row cron-builder__row--inline">
              <label>Day of month</label>
              <input
                type="number"
                className="cron-builder__num"
                min={1}
                max={31}
                value={value.dayOfMonth}
                onChange={(e) => set({ dayOfMonth: parseInt(e.target.value, 10) || 1 })}
              />
            </div>
          )}

          {value.pattern === 'weekly' && (
            <div className="cron-builder__row">
              <label>On days</label>
              <div className="cron-builder__days">
                {WEEKDAY_OPTIONS.map((d) => (
                  <button
                    key={d.value}
                    type="button"
                    className={`cron-builder__day${value.weekDays.includes(d.value) ? ' cron-builder__day--on' : ''}`}
                    onClick={() => toggleWeekDay(d.value)}
                    title={d.label}
                  >
                    {d.short}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="cron-builder__row">
            <label>At time</label>
            <div className="cron-builder__time">
              <TimeField label="Hour" min={0} max={23} value={value.hour} onChange={(h) => set({ hour: h })} />
              <span className="cron-builder__time-sep">:</span>
              <TimeField label="Min" min={0} max={59} value={value.minute} onChange={(m) => set({ minute: m })} />
              <span className="cron-builder__time-sep">:</span>
              <TimeField label="Sec" min={0} max={59} value={value.second} onChange={(s) => set({ second: s })} />
            </div>
          </div>
        </>
      )}

      {value.pattern === 'custom' && (
        <div className="cron-builder__row">
          <label>Cron expression</label>
          <input
            className="cron-builder__input cron-builder__input--mono"
            value={value.customCron}
            onChange={(e) => set({ customCron: e.target.value })}
            placeholder="0 9 * * 1-5  or  30 0 9 * * 1"
          />
          <div className="cron-builder__hint">
            5 fields: minute hour day month weekday · 6 fields (with seconds): second minute hour day month weekday
          </div>
        </div>
      )}

      <div className="cron-builder__preview">
        <div className="cron-builder__summary">{built.summary}</div>
        {built.cron_expr && (
          <code className="cron-builder__expr">{built.cron_expr}</code>
        )}
        {built.interval_seconds != null && (
          <code className="cron-builder__expr">interval {built.interval_seconds}s</code>
        )}
      </div>
    </div>
  )
}

function TimeField({
  label,
  min,
  max,
  value,
  onChange,
}: {
  label: string
  min: number
  max: number
  value: number
  onChange: (n: number) => void
}) {
  return (
    <div className="cron-builder__time-field">
      <span className="cron-builder__time-label">{label}</span>
      <input
        type="number"
        className="cron-builder__num cron-builder__num--time"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const n = parseInt(e.target.value, 10)
          if (Number.isNaN(n)) return
          onChange(Math.min(max, Math.max(min, n)))
        }}
      />
    </div>
  )
}

export { defaultCronScheduleState, buildScheduleFromState, parseScheduleToState } from '@/lib/cronSchedule'
