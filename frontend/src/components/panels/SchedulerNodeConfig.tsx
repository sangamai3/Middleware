import { useEffect, useMemo, useState } from 'react'
import type { CanvasNodeData } from '@/types'
import { CronScheduleBuilder } from '@/components/scheduler/CronScheduleBuilder'
import {
  buildScheduleFromState,
  parseScheduleToState,
  type CronScheduleState,
} from '@/lib/cronSchedule'

function readInterval(cfg: Record<string, unknown>): number | null {
  const raw = cfg.interval_seconds
  if (typeof raw === 'number' && !Number.isNaN(raw)) return raw
  if (raw != null && raw !== '') {
    const n = parseInt(String(raw), 10)
    return Number.isNaN(n) ? null : n
  }
  return null
}

export function SchedulerNodeConfig({
  data,
  onUpdate,
}: {
  data: CanvasNodeData
  onUpdate: (patch: Partial<CanvasNodeData>) => void
}) {
  const cfg = (data.config as Record<string, unknown>) ?? {}
  const cronStr = (cfg.cron as string) || ''
  const interval = readInterval(cfg)
  const configKey = useMemo(() => `${cronStr}|${interval ?? ''}`, [cronStr, interval])

  const [schedule, setSchedule] = useState<CronScheduleState>(() =>
    parseScheduleToState(cronStr || null, interval),
  )

  useEffect(() => {
    setSchedule(parseScheduleToState(cronStr || null, interval))
  }, [configKey, cronStr, interval])

  const applySchedule = (next: CronScheduleState) => {
    setSchedule(next)
    const built = buildScheduleFromState(next)
    const nextCfg: Record<string, unknown> = { ...cfg, schedule_summary: built.summary }
    if (built.interval_seconds != null) {
      nextCfg.interval_seconds = built.interval_seconds
      nextCfg.cron = ''
    } else {
      nextCfg.cron = built.cron_expr ?? ''
      delete nextCfg.interval_seconds
    }
    onUpdate({ config: nextCfg })
  }

  return (
    <div className="scheduler-node-config">
      <div className="config-field">
        <label className="config-label">When to run</label>
        <p className="scheduler-node-config__hint">
          Pick days and time — the cron expression is generated for you.
        </p>
      </div>
      <CronScheduleBuilder value={schedule} onChange={applySchedule} />
    </div>
  )
}
