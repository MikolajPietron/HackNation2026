// Accordion item modelled on Spectrum UI's Accordion (ui.spectrumhq.in/docs/accordion, the
// "card" variant: each item on its own surface whose border firms up while it is open; the
// "plus" indicator turns into a minus on open). The Spectrum source is behind a login, so this is
// written from its description on our tokens: Motion for the height, EASE_OUT under 300 ms, no
// animation with prefers-reduced-motion. Controlled: the caller keeps which items are open.
import { useId } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { EASE_OUT } from '@/lib/ease'
import { cn } from '@/lib/utils'

export function AccordionItem({
  open,
  onToggle,
  title,
  aside,
  variant = 'card',
  indicator = 'plus',
  highlight = false,
  className,
  children,
}: {
  open: boolean
  onToggle: () => void
  /** The trigger's content (left side). */
  title: ReactNode
  /** Shown on the right of the trigger, before the indicator. */
  aside?: ReactNode
  /** card = own bordered surface; ghost = no surface, only a row. */
  variant?: 'card' | 'ghost'
  indicator?: 'plus' | 'chevron'
  /** Something inside changed (the plan was recalculated): the border turns amber. */
  highlight?: boolean
  className?: string
  children: ReactNode
}) {
  const id = useId()
  const reduce = useReducedMotion()
  return (
    <div
      className={cn(
        variant === 'card' &&
          'rounded-3xl border bg-white transition-[border-color,box-shadow] duration-200',
        variant === 'card' &&
          (highlight
            ? 'border-sun-400 shadow-[0_0_0_1px_var(--color-sun-400)]'
            : open
              ? 'border-navy-200 shadow-[0_10px_30px_-22px_rgb(26_36_56/0.35)]'
              : 'border-line hover:border-navy-100'),
        className,
      )}
    >
      <button
        type="button"
        id={`${id}-trigger`}
        aria-expanded={open}
        aria-controls={`${id}-panel`}
        onClick={onToggle}
        className={cn(
          'group flex w-full items-center gap-3 text-left focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
          variant === 'card' ? 'rounded-3xl px-4 py-3 sm:px-5' : 'rounded-2xl px-2 py-2.5 hover:bg-navy-50/60',
        )}
      >
        <span className="min-w-0 flex-1">{title}</span>
        {aside}
        <Indicator kind={indicator} open={open} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="panel"
            id={`${id}-panel`}
            role="region"
            aria-labelledby={`${id}-trigger`}
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={reduce ? { opacity: 0, transition: { duration: 0 } } : { height: 0, opacity: 0, transition: { duration: 0.18, ease: EASE_OUT } }}
            transition={{ duration: 0.28, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/** A plus whose vertical bar folds away into a minus, or a chevron that turns. */
function Indicator({ kind, open }: { kind: 'plus' | 'chevron'; open: boolean }) {
  if (kind === 'chevron') {
    return (
      <svg
        viewBox="0 0 16 16"
        aria-hidden
        className={cn(
          'size-4 shrink-0 text-navy-400 transition-transform duration-200 group-hover:text-navy-700',
          open && 'rotate-180',
        )}
      >
        <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  return (
    <span
      aria-hidden
      className={cn(
        'grid size-8 shrink-0 place-items-center rounded-full transition-colors duration-200',
        open ? 'bg-navy-900 text-white' : 'bg-navy-50 text-navy-500 group-hover:bg-navy-100 group-hover:text-navy-900',
      )}
    >
      <svg viewBox="0 0 16 16" className="size-3.5">
        <path d="M3 8h10" stroke="currentColor" strokeWidth={2} strokeLinecap="round" />
        <path
          d="M8 3v10"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          className={cn('origin-center transition-transform duration-200', open && 'scale-y-0 rotate-90')}
          style={{ transformBox: 'fill-box' }}
        />
      </svg>
    </span>
  )
}
