// "Nie zostawiajcie tego na stole" (FUNKCJE F9): what the family can still use and loses if it
// does nothing, the soonest first, as the engine lists it (`Timeline.left_on_table`). Each line:
// whose right, what, how much (the engine's amount; the screen never adds anything up), and
// until when. A point of no return counts its days down. A click opens the period or the day.
import { motion } from 'motion/react'
import { ChevronRight } from 'lucide-react'
import { Illustration } from '@/components/ui/illustration'
import { formatShortDate } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { ICONS, segmentIcon } from '@/lib/icons'
import { formatPln } from '@/lib/money'
import { COUNTDOWN_DAYS, daysLeftLabel, length } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { Leftover, Timeline } from '@/types'
import { NoReturnTag } from './NextSteps'

const WHO: Record<'mother' | 'father' | 'both', { label: string; dot: string }> = {
  mother: { label: 'Mama', dot: 'bg-zus-600' },
  father: { label: 'Tata', dot: 'bg-navy-700' },
  both: { label: 'Mama albo tata', dot: 'bg-sun-400' },
}

export function LeftOnTable({ timeline, onSelect }: { timeline: Timeline; onSelect: (id: string) => void }) {
  const items = timeline.left_on_table
  if (items.length === 0) return null
  return (
    <section aria-labelledby="left-on-table" className="rounded-4xl border border-line px-4 pt-5 pb-3 sm:px-5">
      <header className="flex items-start gap-3">
        <Illustration src={ICONS.skarbonka} size="event" className="bg-sun-100/70" />
        <div className="min-w-0">
          <h2 id="left-on-table" className="text-lg leading-tight font-bold text-navy-900">
            Nie zostawiajcie tego na stole
          </h2>
          <p className="mt-0.5 text-sm text-navy-500">
            To jeszcze Wam przysługuje. Jeśli nic nie zrobicie, przepadnie.
          </p>
        </div>
      </header>
      <ul className="mt-3 divide-y divide-line">
        {items.map((item, index) => (
          <Row key={item.id} item={item} index={index} timeline={timeline} onSelect={onSelect} />
        ))}
      </ul>
    </section>
  )
}

function Row({
  item,
  index,
  timeline,
  onSelect,
}: {
  item: Leftover
  index: number
  timeline: Timeline
  onSelect: (id: string) => void
}) {
  const segment = timeline.segments.find((s) => s.id === item.segment_id)
  const marker = timeline.markers.find((m) => m.id === item.marker_id)
  const target = segment?.id ?? marker?.id ?? null
  const who = WHO[item.parent ?? 'both']
  const icon = segment ? segmentIcon(segment) : item.kind === 'choice' ? ICONS.pieniadze : ICONS.kalendarz
  const left = marker?.irreversible?.days_left
  const until =
    left !== undefined && left >= 0 && left <= COUNTDOWN_DAYS
      ? `${daysLeftLabel(left)} · do ${formatShortDate(item.last_day)}`
      : `do ${formatShortDate(item.last_day)}`
  const amount = item.amount !== null && item.amount > 0 ? item.amount : null

  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.04, ease: EASE_OUT }}
    >
      <button
        type="button"
        disabled={!target}
        onClick={() => target && onSelect(target)}
        className={cn(
          'group flex w-full items-start gap-3 rounded-2xl px-2 py-3 text-left transition-colors duration-150 sm:gap-4',
          'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none enabled:hover:bg-navy-50/60',
        )}
      >
        <Illustration src={icon} size="event" className="bg-white" />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="flex items-center gap-1.5 text-xs font-bold text-navy-500">
              <span className={cn('size-2 rounded-full', who.dot)} aria-hidden />
              {who.label}
            </span>
            {marker?.irreversible && <NoReturnTag />}
          </span>
          <span className="mt-0.5 block font-bold text-navy-900">{item.title}</span>
          <span className="mt-0.5 line-clamp-2 block text-sm leading-relaxed text-navy-500">{item.text}</span>
          {item.start_by && item.days !== null && (
            <span className="mt-1 block text-sm text-navy-700">
              Żeby wykorzystać całość, zacznij najpóźniej {formatShortDate(item.start_by)}
            </span>
          )}
        </span>
        <span className="flex shrink-0 flex-col items-end gap-0.5 text-right">
          {amount !== null ? (
            <span className="text-base font-bold text-navy-900 tabular-nums sm:text-lg">{formatPln(amount)}</span>
          ) : item.days !== null ? (
            <span className="text-base font-bold text-navy-900 sm:text-lg">{length(item.days)}</span>
          ) : null}
          {amount !== null && item.days !== null && (
            <span className="text-xs font-bold text-navy-400">za {length(item.days)}</span>
          )}
          <span className="text-xs font-bold text-sun-700">{until}</span>
        </span>
        {target && (
          <ChevronRight className="mt-3 size-4 shrink-0 text-navy-300 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-navy-500" />
        )}
      </button>
    </motion.li>
  )
}
