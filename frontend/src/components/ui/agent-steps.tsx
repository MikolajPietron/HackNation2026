// Adapted from Spectrum UI (https://ui.spectrumhq.in, Apache-2.0): blocks/ai-assistants/agent-steps,
// "Compact" variant. Changes: our colour tokens, Polish labels instead of tool names, and a step
// can be a button (jump to the timeline).

import { Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AgentStepStatus = 'running' | 'success' | 'error'

export interface AgentStep {
  id: string
  label: string
  status: AgentStepStatus
  /** Shown after the label, e.g. "pokaż". */
  hint?: string
  hintClassName?: string
  onClick?: () => void
}

export function AgentSteps({ steps, className }: { steps: AgentStep[]; className?: string }) {
  return (
    <ol className={cn('w-full text-[13px]', className)}>
      {steps.map((step, index) => (
        <li key={step.id} className="relative flex gap-2.5">
          <div className="flex flex-col items-center">
            <span className="grid size-5 shrink-0 place-items-center">
              {step.status === 'success' ? (
                <span className="grid size-4 place-items-center rounded-full bg-zus-600/15 text-zus-700 motion-safe:animate-pop">
                  <Check className="size-2.5" strokeWidth={3} />
                </span>
              ) : step.status === 'error' ? (
                <span className="grid size-4 place-items-center rounded-full bg-alert-600/15 text-alert-600 motion-safe:animate-pop">
                  <X className="size-2.5" strokeWidth={3} />
                </span>
              ) : (
                <span className="size-2 rounded-full bg-zus-400 motion-safe:animate-pulse" />
              )}
            </span>
            {index < steps.length - 1 && <span className="w-px flex-1 bg-navy-900/10" />}
          </div>
          <div className={cn('min-w-0 flex-1', index < steps.length - 1 && 'pb-2')}>
            <StepLabel step={step} />
          </div>
        </li>
      ))}
    </ol>
  )
}

function StepLabel({ step }: { step: AgentStep }) {
  const content = (
    <>
      <span
        className={cn(
          'truncate font-bold',
          step.status === 'error' ? 'text-alert-600' : 'text-navy-700',
        )}
      >
        {step.label}
      </span>
      {step.status === 'error' && <span className="shrink-0 text-alert-600">· odrzucone</span>}
      {step.onClick && step.hint && (
        <span className={cn('shrink-0 text-zus-700', step.hintClassName)}>· {step.hint}</span>
      )}
    </>
  )
  const className = 'flex min-h-5 w-full items-center gap-1.5 text-left'
  if (!step.onClick) return <span className={className}>{content}</span>
  return (
    <button
      type="button"
      onClick={step.onClick}
      className={cn(
        className,
        'rounded transition-transform duration-150 active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-hidden',
      )}
    >
      {content}
    </button>
  )
}
