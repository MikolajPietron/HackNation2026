// A modal over the whole app for the simulated integrations, and the badge that marks every
// simulation (FUNKCJE: simulations are clearly marked as example data). The panel always fits
// the screen and scrolls inside (components/ui/modal-panel); on phones it comes up from the bottom.
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'motion/react'
import { ModalPanel } from '@/components/ui/modal-panel'
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
          className="fixed inset-0 z-50 flex items-end justify-center bg-navy-900/15 backdrop-blur-[3px] sm:items-center sm:p-6 lg:p-10"
        >
          <ModalPanel label={label} onClose={onClose} sheetOnPhone className={cn('max-w-lg', className)}>
            {children}
          </ModalPanel>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
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
