import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import './Toast.css'

type ToastType = 'success' | 'error' | 'info' | 'warn'

interface ToastItem {
  id: string
  message: string
  type: ToastType
}

interface ToastCtx {
  success: (msg: string) => void
  error: (msg: string) => void
  info: (msg: string) => void
  warn: (msg: string) => void
}

const ToastContext = createContext<ToastCtx>({
  success: () => {}, error: () => {}, info: () => {}, warn: () => {},
})

export function useToast() { return useContext(ToastContext) }

function ToastEl({ item, onDone }: { item: ToastItem; onDone: (id: string) => void }) {
  const [exit, setExit] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    timer.current = setTimeout(() => setExit(true), 3500)
    return () => clearTimeout(timer.current)
  }, [])

  useEffect(() => {
    if (!exit) return
    const t = setTimeout(() => onDone(item.id), 280)
    return () => clearTimeout(t)
  }, [exit, item.id, onDone])

  const ICONS: Record<ToastType, string> = {
    success: '✓', error: '✕', info: 'ℹ', warn: '⚠',
  }

  return (
    <div className={`toast toast--${item.type}${exit ? ' toast--exit' : ''}`} role="status">
      <span className="toast__icon">{ICONS[item.type]}</span>
      <span className="toast__msg">{item.message}</span>
      <button className="toast__close" onClick={() => setExit(true)} aria-label="Dismiss">×</button>
    </div>
  )
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  let counter = useRef(0)

  const add = useCallback((message: string, type: ToastType) => {
    const id = `t${++counter.current}`
    setToasts(prev => [...prev.slice(-4), { id, message, type }])
  }, [])

  const remove = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const ctx: ToastCtx = {
    success: (msg) => add(msg, 'success'),
    error:   (msg) => add(msg, 'error'),
    info:    (msg) => add(msg, 'info'),
    warn:    (msg) => add(msg, 'warn'),
  }

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      <div className="toast-container" aria-live="polite">
        {toasts.map(t => <ToastEl key={t.id} item={t} onDone={remove} />)}
      </div>
    </ToastContext.Provider>
  )
}
