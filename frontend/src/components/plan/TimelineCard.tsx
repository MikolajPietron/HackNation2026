// The timeline with its summary underneath, in one card. "Rozwiń" opens the same axis over the
// whole plan column, zoomed in, for a closer look; Escape or "Zwiń" brings it back.
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'motion/react'
import { EASE_OUT } from '@/lib/ease'
import type { Timeline } from '@/types'
import { PlanAgenda } from './PlanAgenda'
import { PlanTimeline } from './PlanTimeline'

interface Props {
  timeline: Timeline
  changedIds: Set<string>
  changeVersion: number
  selectedId: string | null
  onSelect: (id: string) => void
  /** Layer over the plan column for the expanded axis (sections below have filters, which
   * would trap an absolutely positioned overlay inside them). */
  overlayRoot: HTMLElement | null
}

export function TimelineCard({ overlayRoot, ...props }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (!expanded) return
    const onKey = (event: KeyboardEvent) => {
      // Details opened from the expanded axis close first.
      if (event.key === 'Escape' && !document.querySelector('[aria-modal="true"]')) setExpanded(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])

  const content = (zoom: number, isExpanded: boolean) => (
    <>
      <PlanTimeline
        {...props}
        hoveredId={hovered}
        onHover={setHovered}
        initialZoom={zoom}
        expanded={isExpanded}
        preview
        onToggleExpanded={() => setExpanded(!isExpanded)}
      />
      <PlanAgenda
        timeline={props.timeline}
        hoveredId={hovered}
        onHover={setHovered}
        onSelect={props.onSelect}
      />
    </>
  )

  const overlay = (
    <AnimatePresence>
      {expanded && (
        <motion.div
          key="expanded"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.15 } }}
          transition={{ duration: 0.2, ease: EASE_OUT }}
          className="pointer-events-auto absolute inset-0 overflow-y-auto bg-white/80 p-6 backdrop-blur-[3px]"
        >
          <motion.div
            role="dialog"
            aria-label="Oś czasu"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.99, transition: { duration: 0.15 } }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            className="min-h-full rounded-4xl border border-line bg-white px-6 pt-4 pb-3 shadow-[0_24px_60px_-30px_rgb(26_36_56/0.28)]"
          >
            {content(2.25, true)}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )

  return (
    <>
      <div className="rounded-4xl border border-line px-5 pt-4 pb-3">{content(1, false)}</div>
      {overlayRoot && createPortal(overlay, overlayRoot)}
    </>
  )
}
