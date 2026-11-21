// Two ways to see the same plan: the axis (or the list on phones) and the wall calendar. A pill
// slides between them on a spring; the choice is remembered on this device (usePlanView).
import { useId } from 'react'
import { motion } from 'motion/react'
import type { PlanView } from '@/hooks/usePlanView'
import { cn } from '@/lib/utils'

export function ViewSwitch({
  view,
  onChange,
  axisLabel = 'Oś',
  className,
}: {
  view: PlanView
  onChange: (view: PlanView) => void
  axisLabel?: string
  className?: string
}) {
  const id = useId()
  const options: { id: PlanView; label: string }[] = [
    { id: 'axis', label: axisLabel },
    { id: 'calendar', label: 'Kalendarz' },
  ]
  return (
    <div role="tablist" aria-label="Widok planu" className={cn('flex rounded-full bg-navy-50 p-0.5', className)}>
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          role="tab"
          aria-selected={view === option.id}
          onClick={() => onChange(option.id)}
          className={cn(
            'relative rounded-full px-3 py-1.5 text-xs font-bold transition-colors duration-150',
            view === option.id ? 'text-navy-900' : 'text-navy-500 hover:text-navy-900',
          )}
        >
          {view === option.id && (
            <motion.span
              layoutId={`plan-view-${id}`}
              className="absolute inset-0 rounded-full bg-white shadow-sm"
              transition={{ type: 'spring', duration: 0.3, bounce: 0.15 }}
            />
          )}
          <span className="relative">{option.label}</span>
        </button>
      ))}
    </div>
  )
}
