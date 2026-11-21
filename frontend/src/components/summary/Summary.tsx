import { FileText } from 'lucide-react'
import { NavListCard } from '@/components/ui/nav-list-card'
import { NumberTicker } from '@/components/ui/number-ticker'
import { dayNumber, formatDate } from '@/lib/dates'
import { cn } from '@/lib/utils'
import type { Timeline } from '@/types'

// Solid green, soft green, navy: the three tiles of the reference dashboard in ZUS colours.
const TILE_TONES = ['bg-zus-600 text-white', 'bg-zus-200 text-zus-900', 'bg-navy-700 text-white']

/** How much leave there is, at a glance. A tile jumps to its leave on the timeline. */
export function SummaryTiles({
  timeline,
  onSelect,
  className,
}: {
  timeline: Timeline
  onSelect: (id: string) => void
  className?: string
}) {
  return (
    <div className={cn('grid grid-cols-3 gap-2.5', className)}>
      {timeline.summary.map((stat, index) => (
        <button
          key={stat.id}
          type="button"
          onClick={() => onSelect(stat.segment_ids.at(-1) ?? stat.id)}
          className={cn(
            'rounded-2xl px-3 py-3 text-left transition-transform duration-150 hover:-translate-y-0.5 active:scale-[0.97]',
            TILE_TONES[index % TILE_TONES.length],
          )}
        >
          <span className="block truncate text-[11px] font-bold opacity-85">{stat.label}</span>
          <span className="mt-1 flex items-baseline gap-1">
            <NumberTicker value={stat.value} className="text-2xl leading-none font-black" />
            <span className="text-xs font-bold opacity-85">{stat.unit}</span>
          </span>
        </button>
      ))}
    </div>
  )
}

/** Applications in the order they are due. */
export function ApplicationsList({
  timeline,
  selectedId,
  onSelect,
  className,
}: {
  timeline: Timeline
  selectedId: string | null
  onSelect: (id: string) => void
  className?: string
}) {
  const applications = [...timeline.applications].sort(
    (a, b) => dayNumber(a.due) - dayNumber(b.due),
  )
  return (
    <NavListCard
      title="Wnioski i terminy"
      className={className}
      items={applications.map((a) => ({
        id: a.id,
        icon: <FileText />,
        iconClassName: a.passed
          ? 'bg-alert-50 text-alert-600'
          : a.parent === 'mother'
            ? 'bg-zus-100 text-zus-700'
            : 'bg-navy-100 text-navy-700',
        label: a.title,
        meta: a.passed
          ? `termin minął ${formatDate(a.due)}`
          : a.is_deadline
            ? `do ${formatDate(a.due)}`
            : `na ${formatDate(a.due)}`,
        metaClassName: a.passed ? 'text-alert-600' : undefined,
        selected: a.id === selectedId,
        onSelect: () => onSelect(a.id),
      }))}
    />
  )
}
