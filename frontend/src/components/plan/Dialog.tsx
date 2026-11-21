// A dialog over the plan column (the chat beside it stays usable). The panel always fits the
// column and scrolls inside (components/ui/modal-panel); a click outside closes it.
import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { ModalPanel } from '@/components/ui/modal-panel'
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
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.15 } }}
      transition={{ duration: 0.2, ease: EASE_OUT }}
      onClick={onClose}
      className="absolute inset-0 z-30 flex items-center justify-center bg-white/75 p-6 backdrop-blur-[3px] lg:p-10"
    >
      <ModalPanel label={label} onClose={onClose} className="max-w-xl">
        {children}
      </ModalPanel>
    </motion.div>
  )
}
