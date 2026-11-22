// What is wrong with one field, right under it: a short line with an icon, red for an error, amber
// for "sprawdź", navy for a note. It opens smoothly (height and opacity; only a fade with reduced
// motion) and the field points at it with `aria-describedby`, so a screen reader reads it with the
// field. The field itself turns red through `fieldLook` (hooks/useFieldErrors.ts).
import type { ReactNode } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { CircleAlert, Info, TriangleAlert } from 'lucide-react'
import { EASE_OUT } from '@/lib/ease'
import { cn } from '@/lib/utils'

export type FieldTone = 'error' | 'warning' | 'info'

export interface FieldIssue {
  /** Stable while the issue lasts, so a changing text ("brakuje 2" → "brakuje 1") does not re-enter. */
  key: string
  tone: FieldTone
  text: ReactNode
  /** A smaller line under the text: the rule behind it, sources, "Pokaż na osi". */
  extra?: ReactNode
}

const LOOK: Record<FieldTone, { icon: typeof Info; tone: string }> = {
  error: { icon: CircleAlert, tone: 'text-alert-600' },
  warning: { icon: TriangleAlert, tone: 'text-sun-700' },
  info: { icon: Info, tone: 'text-navy-500' },
}

export function FieldError({ id, issues, className }: { id: string; issues: FieldIssue[]; className?: string }) {
  const reduce = useReducedMotion()
  return (
    <div id={id} className={className}>
      <AnimatePresence initial={false}>
        {issues.map((issue) => {
          const look = LOOK[issue.tone]
          const Icon = look.icon
          return (
            <motion.div
              key={issue.key}
              initial={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0, transition: { duration: 0.15, ease: EASE_OUT } }}
              transition={{ duration: reduce ? 0.12 : 0.24, ease: EASE_OUT }}
              className="overflow-hidden"
            >
              <div className={cn('flex gap-1.5 pt-1.5 text-left text-[13px] leading-snug font-normal', look.tone)}>
                <Icon className="mt-[2px] size-3.5 shrink-0" aria-hidden />
                <div className="min-w-0">
                  <p>{issue.text}</p>
                  {issue.extra}
                </div>
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
