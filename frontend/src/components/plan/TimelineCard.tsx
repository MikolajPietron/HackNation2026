// The timeline with what lies ahead underneath, in one card. The switch at the top shows the
// same plan as a wall calendar. "Rozwiń" opens the axis (zoomed in) or the calendar (large, with
// the periods named and a panel for the chosen day) over the whole plan column for a closer
// look; Escape or "Zwiń" brings it back.
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'motion/react'
import { usePlanView } from '@/hooks/usePlanView'
import { EASE_OUT } from '@/lib/ease'
import { cn } from '@/lib/utils'
import type { Timeline } from '@/types'
import { NextSteps } from './NextSteps'
import { PlanTimeline } from './PlanTimeline'
import { ViewSwitch } from './ViewSwitch'
import { YearCalendar } from './YearCalendar'

interface Props {
  timeline: Timeline
  changedIds: Set<string>
  changeVersion: number
  selectedId: string | null
  onSelect: (id: string) => void
  /** Layer over the plan column for the expanded axis (sections below have filters, which
   * would trap an absolutely positioned overlay inside them). */
  overlayRoot: HTMLElement | null
  /** After a change of the plan: the playhead goes to this day. */
  focus?: { day: number; key: number } | null
  /** A what-if is shown instead of the plan: the card says so with a dashed amber edge. */
  preview?: boolean
}

export function TimelineCard({ overlayRoot, preview = false, ...props }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [view, setView] = usePlanView()

  useEffect(() => {
    if (!expanded) return
    const onKey = (event: KeyboardEvent) => {
      // Details opened from the expanded axis close first.
      if (event.key === 'Escape' && !document.querySelector('[aria-modal="true"]')) setExpanded(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])

  const axis = (zoom: number, isExpanded: boolean) => (
    <PlanTimeline
      {...props}
      hoveredId={hovered}
      onHover={setHovered}
      initialZoom={zoom}
      expanded={isExpanded}
      onToggleExpanded={() => setExpanded(!isExpanded)}
      toolbarStart={isExpanded ? undefined : <ViewSwitch view={view} onChange={setView} className="mr-2" />}
    />
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
            aria-label={view === 'axis' ? 'Oś czasu' : 'Kalendarz'}
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.99, transition: { duration: 0.15 } }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            className={cn(
              'min-h-full rounded-4xl border border-line bg-white px-6 shadow-[0_24px_60px_-30px_rgb(26_36_56/0.28)]',
              view === 'axis' ? 'pt-4 pb-3' : 'pt-4 pb-10',
            )}
          >
            {view === 'axis' ? (
              axis(2.25, true)
            ) : (
              <YearCalendar
                timeline={props.timeline}
                onSelect={props.onSelect}
                size="large"
                onCollapse={() => setExpanded(false)}
              />
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )

  return (
    <>
      <div
        className={cn(
          'rounded-4xl border px-5 pt-4 pb-5 transition-[border-color,background-color] duration-300',
          preview ? 'border-2 border-dashed border-sun-400 bg-sun-100/15' : 'border-line',
        )}
      >
        {view === 'axis' ? (
          axis(1, false)
        ) : (
          <YearCalendar
            timeline={props.timeline}
            onSelect={props.onSelect}
            headerStart={<ViewSwitch view={view} onChange={setView} className="w-fit" />}
            onExpand={() => setExpanded(true)}
          />
        )}
        <NextSteps
          timeline={props.timeline}
          changedIds={props.changedIds}
          changeVersion={props.changeVersion}
          hoveredId={hovered}
          onHover={setHovered}
          onSelect={props.onSelect}
        />
      </div>
      {overlayRoot && createPortal(overlay, overlayRoot)}
    </>
  )
}
