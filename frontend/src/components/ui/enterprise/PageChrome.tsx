import type { ReactNode } from 'react'
import './PageChrome.css'

export function PageHeader({
  title,
  description,
  meta,
  actions,
}: {
  title: string
  description?: ReactNode
  meta?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="ep-header">
      <div className="ep-header__main">
        {meta && <div className="ep-header__meta">{meta}</div>}
        <h1 className="ep-header__title">{title}</h1>
        {description && <p className="ep-header__desc">{description}</p>}
      </div>
      {actions && <div className="ep-header__actions">{actions}</div>}
    </header>
  )
}

export function KpiGrid({
  items,
}: {
  items: {
    id: string
    label: string
    value: string | number
    hint?: string
    tone?: 'default' | 'accent' | 'success' | 'danger' | 'warn'
  }[]
}) {
  return (
    <div className="ep-kpi-grid" role="list">
      {items.map((k) => (
        <div
          key={k.id}
          className={`ep-kpi ep-kpi--${k.tone ?? 'default'}`}
          role="listitem"
        >
          <div className="ep-kpi__label">{k.label}</div>
          <div className="ep-kpi__value">{k.value}</div>
          {k.hint && <div className="ep-kpi__hint">{k.hint}</div>}
        </div>
      ))}
    </div>
  )
}

export function SurfaceCard({
  title,
  subtitle,
  action,
  children,
  className = '',
  noPadding,
}: {
  title?: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
  noPadding?: boolean
}) {
  return (
    <section className={`ep-card ${className}`.trim()}>
      {(title || action) && (
        <div className="ep-card__head">
          <div>
            {title && <h2 className="ep-card__title">{title}</h2>}
            {subtitle && <p className="ep-card__sub">{subtitle}</p>}
          </div>
          {action && <div className="ep-card__action">{action}</div>}
        </div>
      )}
      <div className={noPadding ? 'ep-card__body ep-card__body--flush' : 'ep-card__body'}>
        {children}
      </div>
    </section>
  )
}

export function EmptyPanel({
  icon,
  title,
  description,
  action,
}: {
  icon?: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="ep-empty">
      {icon && <div className="ep-empty__icon" aria-hidden>{icon}</div>}
      <div className="ep-empty__title">{title}</div>
      {description && <p className="ep-empty__desc">{description}</p>}
      {action && <div className="ep-empty__action">{action}</div>}
    </div>
  )
}

export function FlowStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    deployed: 'ep-status--success',
    draft: 'ep-status--muted',
    failed: 'ep-status--danger',
    paused: 'ep-status--warn',
    archived: 'ep-status--muted',
  }
  return (
    <span className={`ep-status ${map[status] ?? 'ep-status--muted'}`}>
      <span className="ep-status__dot" />
      {status}
    </span>
  )
}
