// Adapted from Spectrum UI (https://ui.spectrumhq.in, Apache-2.0): animated-drawer, built on
// Vaul (Emil Kowalski's drawer). Changes: our tokens, a reusable shell instead of the wallet demo,
// optional full height for scrolling content (the chat), screen-reader title.
//
// Vaul brings what Emil's guide asks of a sheet: drag to dismiss with velocity (a flick is
// enough), damping past the edge, pointer capture, and an iOS-like drawer curve. When the content
// changes size the sheet glides to the new height (react-use-measure + Motion), as in the demo.
import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import useMeasure from 'react-use-measure'
import { Drawer } from 'vaul'
import { EASE_DRAWER } from '@/lib/ease'
import { cn } from '@/lib/utils'

export function Sheet({
  open,
  onOpenChange,
  title,
  fullHeight = false,
  className,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** For screen readers; the content shows its own heading. */
  title: string
  /** A fixed tall sheet whose content scrolls inside (e.g. the chat). */
  fullHeight?: boolean
  className?: string
  children: ReactNode
}) {
  const [inner, bounds] = useMeasure()
  return (
    <Drawer.Root open={open} onOpenChange={onOpenChange}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-50 bg-navy-900/25 backdrop-blur-[2px]" />
        <Drawer.Content
          aria-describedby={undefined}
          className={cn(
            'fixed inset-x-0 bottom-0 z-50 flex max-h-[92dvh] flex-col rounded-t-[28px] bg-white outline-none',
            fullHeight && 'h-[92dvh]',
            className,
          )}
        >
          <Drawer.Title className="sr-only">{title}</Drawer.Title>
          <div aria-hidden className="mx-auto mt-3 mb-1 h-1.5 w-12 shrink-0 rounded-full bg-navy-100" />
          {fullHeight ? (
            <div className="min-h-0 flex-1">{children}</div>
          ) : (
            <motion.div
              animate={{ height: bounds.height || 'auto' }}
              transition={{ duration: 0.35, ease: EASE_DRAWER }}
              data-scroll
              className="scrollbar-soft min-h-0 overflow-y-auto overscroll-contain"
            >
              <div ref={inner} className="px-5 pt-2 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
                {children}
              </div>
            </motion.div>
          )}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  )
}
