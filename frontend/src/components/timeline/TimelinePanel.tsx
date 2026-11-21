import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { TriangleAlert, X } from 'lucide-react'
import { TextStates } from '@/components/ui/text-states'
import type { ChangeSet } from '@/hooks/useAssistant'
import { formatLongDate } from '@/lib/dates'
import { EASE_OUT, SPRING_LAYOUT } from '@/lib/ease'
import { cn } from '@/lib/utils'
import type { Timeline } from '@/types'
import { ElementDetails } from './ElementDetails'
import { EmptyTimeline } from './EmptyTimeline'
import { timelineItems } from './items'
import { PillTimeline } from './PillTimeline'
import { VerticalTimeline } from './VerticalTimeline'

type View = 'axis' | 'list'
const VIEWS: { id: View; label: string }[] = [
  { id: 'axis', label: 'Oś' },
  { id: 'list', label: 'Lista' },
]

interface Props {
  timeline: Timeline | null
  changed: ChangeSet
  selectedId: string | null
  focus: { id: string | null; tick: number }
  onSelect: (id: string | null) => void
}

export function TimelinePanel({ timeline, changed, selectedId, focus, onSelect }: Props) {
  const [view, setView] = useState<View>('axis')
  const items = useMemo(() => (timeline ? timelineItems(timeline) : []), [timeline])
  const changedIds = useMemo(() => new Set(changed.ids), [changed])

  if (!timeline) {
    return (
      <div className="p-5 lg:px-8 lg:pt-2 lg:pb-8">
        <EmptyTimeline />
      </div>
    )
  }

  const selected = items.find((item) => item.id === selectedId) ?? null
  const props = { timeline, items, selectedId, changedIds, changeVersion: changed.version, focus, onSelect }
  const due = `Przewidywana data porodu: ${formatLongDate(timeline.due_date)}`

  return (
    // The pill axis needs room; in a narrow column (phone, small laptop) the list takes over.
    <div className="@container">
      <div className="space-y-5 p-5 lg:px-8 lg:pt-2 lg:pb-8">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-black text-navy-900 lg:text-3xl">Twoja oś czasu</h1>
            <p className="mt-1 text-sm font-bold text-navy-500">
              <TextStates text={due} />
            </p>
          </div>
          <div className="hidden rounded-full bg-white p-1 shadow-card @2xl:flex" role="tablist">
            {VIEWS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={view === id}
                onClick={() => setView(id)}
                className={cn(
                  'relative rounded-full px-4 py-1.5 text-xs font-bold transition-colors',
                  view === id ? 'text-white' : 'text-navy-500 hover:text-navy-900',
                )}
              >
                {view === id && (
                  <motion.span
                    layoutId="timeline-view"
                    transition={SPRING_LAYOUT}
                    className="absolute inset-0 rounded-full bg-zus-600"
                  />
                )}
                <span className="relative">{label}</span>
              </button>
            ))}
          </div>
        </header>

        {timeline.warnings.map((warning) => (
          <p
            key={warning}
            className="flex gap-2.5 rounded-2xl bg-sun-100 px-4 py-3 text-sm text-sun-700"
          >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            {warning}
          </p>
        ))}

        {view === 'axis' && (
          <div className="hidden space-y-4 @2xl:block">
            <PillTimeline {...props} />
            <AnimatePresence mode="wait">
              {selected ? (
                <motion.div
                  key={selected.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.22, ease: EASE_OUT }}
                  className="relative rounded-3xl bg-white p-6 shadow-card"
                >
                  <button
                    type="button"
                    onClick={() => onSelect(null)}
                    aria-label="Zamknij szczegóły"
                    className="absolute top-4 right-4 grid size-8 place-items-center rounded-full text-navy-500 transition-colors hover:bg-navy-50 hover:text-navy-900"
                  >
                    <X className="size-4" />
                  </button>
                  <ElementDetails item={selected} timeline={timeline} onSelect={onSelect} />
                </motion.div>
              ) : (
                <motion.p
                  key="hint"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="px-1 text-sm text-navy-500"
                >
                  Kliknij element osi, żeby zobaczyć zasadę i cytat z Przewodnika ZUS.
                </motion.p>
              )}
            </AnimatePresence>
          </div>
        )}
        <div className={cn(view === 'axis' && '@2xl:hidden')}>
          <VerticalTimeline {...props} />
        </div>
      </div>
    </div>
  )
}
