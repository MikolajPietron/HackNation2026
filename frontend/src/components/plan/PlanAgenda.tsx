// "W skrócie": every element of the axis in date order, each in a sentence or two, so the plan
// reads at a glance without opening anything. Hovering a row lights up its element on the axis
// (and the other way round); clicking opens the full details with the source.
import { ChevronRight } from 'lucide-react'
import { Emphasis } from '@/components/ui/emphasis'
import { Illustration } from '@/components/ui/illustration'
import { dayNumber, formatDayMonthShort } from '@/lib/dates'
import { documentIcon, markerIcon, segmentIcon } from '@/lib/icons'
import { cn } from '@/lib/utils'
import type { Timeline } from '@/types'

interface Row {
  id: string
  day: number
  when: string
  icon: string
  title: string
  text: string
}

function rows(timeline: Timeline): Row[] {
  return [
    ...timeline.segments.map((s) => ({
      id: s.id,
      day: dayNumber(s.start),
      when: `${formatDayMonthShort(s.start)} – ${formatDayMonthShort(s.end)}`,
      icon: segmentIcon(s),
      title: s.title,
      text: s.summary,
    })),
    ...timeline.markers.map((m) => ({
      id: m.id,
      day: dayNumber(m.date),
      when: formatDayMonthShort(m.date),
      icon: markerIcon(m),
      title: m.title,
      text: m.summary,
    })),
    ...timeline.documents.map((d) => ({
      id: d.id,
      day: dayNumber(d.needed_by),
      when: `do ${formatDayMonthShort(d.needed_by)}`,
      icon: documentIcon(d),
      title: d.done ? `${d.title} — już jest` : d.title,
      text: d.rule,
    })),
  ].sort((a, b) => a.day - b.day)
}

export function PlanAgenda({
  timeline,
  hoveredId,
  onHover,
  onSelect,
}: {
  timeline: Timeline
  hoveredId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}) {
  return (
    <section aria-label="W skrócie" className="border-t border-line pt-5">
      <h3 className="px-3 text-sm font-bold text-navy-900">W skrócie</h3>
      <ul className="mt-2 gap-x-6 lg:columns-2">
        {rows(timeline).map((row) => (
          <li key={row.id} className="break-inside-avoid">
            <button
              type="button"
              onClick={() => onSelect(row.id)}
              onMouseEnter={() => onHover(row.id)}
              onMouseLeave={() => onHover(null)}
              onFocus={() => onHover(row.id)}
              onBlur={() => onHover(null)}
              className={cn(
                'group flex w-full gap-3 rounded-2xl px-3 py-3 text-left transition-[background-color,transform] duration-150 active:scale-[0.99]',
                'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                hoveredId === row.id && 'bg-navy-50',
              )}
            >
              <span className="w-[5.5rem] shrink-0 pt-px text-sm font-bold whitespace-nowrap text-navy-500 tabular-nums">
                {row.when}
              </span>
              <Illustration src={row.icon} size="event" className="-mt-1.5 bg-navy-50/60" />
              <span className="min-w-0 flex-1">
                <span className="block leading-snug font-bold text-navy-900">{row.title}</span>
                <span className="mt-0.5 line-clamp-2 text-sm leading-relaxed text-navy-500">
                  <Emphasis text={row.text} className="text-navy-700" />
                </span>
              </span>
              <ChevronRight className="mt-0.5 size-4 shrink-0 text-navy-300 opacity-0 transition-opacity group-hover:opacity-100" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
