import './WizardStepper.css'

export interface WizardStep {
  id: string
  label: string
}

interface Props {
  steps: WizardStep[]
  currentId: string
  onGoTo?: (id: string) => void
}

export function WizardStepper({ steps, currentId, onGoTo }: Props) {
  const currentIndex = steps.findIndex((s) => s.id === currentId)

  return (
    <nav className="wiz-stepper" aria-label="Setup progress">
      {steps.map((step, i) => {
        const done = i < currentIndex
        const active = step.id === currentId
        const clickable = onGoTo && i <= currentIndex
        return (
          <button
            key={step.id}
            type="button"
            className={`wiz-stepper__item${active ? ' wiz-stepper__item--active' : ''}${done ? ' wiz-stepper__item--done' : ''}`}
            disabled={!clickable}
            onClick={() => clickable && onGoTo?.(step.id)}
            title={step.label}
          >
            <span className="wiz-stepper__dot">{done ? '✓' : i + 1}</span>
            <span className="wiz-stepper__label">{step.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
