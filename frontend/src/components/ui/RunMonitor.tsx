import { useEffect, useRef, useState } from 'react'
import { subscribeToRun } from '@/api/client'
import type { FlowEvent } from '@/types'
import './RunMonitor.css'

interface Props {
  executionId: string
  onComplete?: (status: 'success' | 'error') => void
}

function eventSeverity(type: string): 'error' | 'success' | 'info' {
  if (type === 'run.failed' || type === 'step.failed') return 'error'
  if (type === 'run.completed') return 'success'
  return 'info'
}

export function RunMonitor({ executionId, onComplete }: Props) {
  const [events, setEvents] = useState<FlowEvent[]>([])
  const [status, setStatus] = useState<'running' | 'success' | 'error' | 'connecting'>('connecting')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const unsubscribe = subscribeToRun(executionId, (raw) => {
      setEvents(prev => [...prev, raw])

      if (raw.type === 'run.completed') {
        setStatus('success')
        onComplete?.('success')
      } else if (raw.type === 'run.failed') {
        setStatus('error')
        onComplete?.('error')
      } else {
        setStatus('running')
      }
    })

    return () => unsubscribe()
  }, [executionId, onComplete])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  return (
    <div className="run-monitor">
      <div className="run-monitor__header">
        <span className="run-monitor__title">Execution monitor</span>
        <span className={`run-status run-status--${status}`}>{status}</span>
      </div>
      <div className="run-monitor__feed">
        {events.length === 0 && (
          <div className="run-monitor__empty">Waiting for events…</div>
        )}
        {events.map((e, i) => (
          <div key={i} className={`run-event run-event--${eventSeverity(e.type)}`}>
            <span className="run-event__time">{new Date(e.timestamp).toLocaleTimeString()}</span>
            <span className="run-event__type">{e.type}</span>
            {e.step_id && <span className="run-event__step">{e.step_id}</span>}
            <span className="run-event__msg">{String(e.payload?.message ?? e.payload?.error ?? '')}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
