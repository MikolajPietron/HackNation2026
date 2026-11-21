// The panel of every dialog (details, "Dlaczego tak?", the simulated services). It always fits
// the screen: only its content scrolls (without dragging the page under it along), and the close
// button stays in its corner. Motion after Emil Kowalski: from scale 0.96 with opacity, ease-out
// under 300 ms, a faster exit; a sheet from the bottom on phones when asked.
// Escape and the close button close it; the backdrop around it is the caller's.
import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { X } from 'lucide-react'
import { EASE_OUT } from '@/lib/ease'
import { cn } from '@/lib/utils'

export function ModalPanel({
  label,
  onClose,
  sheetOnPhone = false,
  className,
  children,
}: {
  label: string
  onClose: () => void
  /** On phones the panel comes up from the bottom edge like a sheet. */
  sheetOnPhone?: boolean
  className?: string
  children: ReactNode
}) {
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    panel.current?.focus({ preventScroll: true })
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
      initial={{ opacity: 0, scale: 0.96, y: sheetOnPhone ? 24 : 0 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98, y: sheetOnPhone ? 12 : 0, transition: { duration: 0.15 } }}
      transition={{ duration: 0.25, ease: EASE_OUT }}
      className={cn(
        'relative flex w-full flex-col overflow-hidden border border-line bg-white shadow-[0_32px_80px_-32px_rgb(26_36_56/0.35)] outline-none',
        sheetOnPhone
          ? 'max-h-[92dvh] rounded-t-4xl border-b-0 sm:max-h-full sm:rounded-4xl sm:border-b'
          : 'max-h-full rounded-4xl',
        className,
      )}
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Zamknij"
        className="absolute top-4 right-4 z-10 grid size-10 place-items-center rounded-full bg-white/90 text-navy-400 backdrop-blur-sm transition-[color,background-color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.94] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
      >
        <X className="size-5" />
      </button>
      <div
        data-scroll
        className="scrollbar-soft min-h-0 flex-1 overflow-y-auto overscroll-contain p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] sm:p-8"
      >
        {children}
      </div>
    </motion.div>
  )
}
