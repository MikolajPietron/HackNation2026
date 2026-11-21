// A dialog over the plan column (the chat beside it stays usable). Motion after Emil Kowalski's
// rules: centred (a modal keeps its origin), from scale 0.96 with opacity, ease-out under 300 ms,
// and a faster exit. Escape, the close button and a click outside close it.
import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { X } from 'lucide-react'
import { EASE_OUT } from '@/lib/ease'

export function Dialog({
  label,
  onClose,
  children,
}: {
  label: string
  onClose: () => void
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
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.15 } }}
      transition={{ duration: 0.2, ease: EASE_OUT }}
      onClick={onClose}
      className="absolute inset-0 z-30 flex items-start justify-center overflow-y-auto bg-white/75 px-8 pt-24 pb-12 backdrop-blur-[3px]"
    >
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
        className="relative w-full max-w-xl rounded-4xl border border-line bg-white p-8 shadow-[0_24px_60px_-30px_rgb(26_36_56/0.28)] outline-none"
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
    </motion.div>
  )
}
