// A modal over the whole app for the simulated integrations, and the badge that marks every
// simulation (FUNKCJE: simulations are clearly marked as example data). Motion after Emil
// Kowalski: centred, from scale 0.96 with opacity, ease-out under 300 ms, faster exit.
import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'motion/react'
import { X } from 'lucide-react'
import { EASE_OUT } from '@/lib/ease'
import { cn } from '@/lib/utils'

export function MockModal({
  open,
  label,
  onClose,
  className,
  children,
}: {
  open: boolean
  label: string
  onClose: () => void
  className?: string
  children: ReactNode
}) {
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.15 } }}
          transition={{ duration: 0.2, ease: EASE_OUT }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-navy-900/15 px-6 pt-[8vh] pb-10 backdrop-blur-[3px]"
        >
          <Panel label={label} onClose={onClose} className={className}>
            {children}
          </Panel>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

function Panel({
  label,
  onClose,
  className,
  children,
}: {
  label: string
  onClose: () => void
  className?: string
  children: ReactNode
}) {
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    panel.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <motion.div
      ref={panel}
      role="dialog"
      aria-modal="true"
      aria-label={label}
      tabIndex={-1}
      onClick={(event) => event.stopPropagation()}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.15 } }}
      transition={{ duration: 0.25, ease: EASE_OUT }}
      className={cn(
        'relative w-full max-w-lg rounded-4xl border border-line bg-white p-8 shadow-[0_32px_80px_-32px_rgb(26_36_56/0.35)] outline-none',
        className,
      )}
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Zamknij"
        className="absolute top-5 right-5 grid size-10 place-items-center rounded-full text-navy-400 transition-[color,background-color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.94] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
      >
        <X className="size-5" />
      </button>
      {children}
    </motion.div>
  )
}

/** Marks a simulated integration or example data. */
export function SimBadge({ children = 'symulacja · dane przykładowe' }: { children?: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-sun-100 px-2.5 py-1 text-[11px] font-bold text-sun-700">
      <span className="size-1.5 rounded-full bg-sun-400" />
      {children}
    </span>
  )
}
