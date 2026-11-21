// "Co przed Wami": what lies ahead, in one column read from top to bottom, grouped by when it
// matters (now, within three months, later). One line per step: a calendar page with the date,
// what it is, and how long until it; what is still to decide carries a tag. No descriptions:
// the details (with the source) open on a click, and a hover lights the element up on the axis.
import { motion } from 'motion/react'
import { ChevronRight } from 'lucide-react'
import { Pulse } from '@/components/timeline/Pulse'
import { Illustration } from '@/components/ui/illustration'
import { EASE_OUT } from '@/lib/ease'
import { nextSteps } from '@/lib/plan'
import type { Step, StepGroup } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { Timeline } from '@/types'

const GROUPS: { id: StepGroup; label: string }[] = [
  { id: 'now', label: 'Teraz' },
  { id: 'soon', label: 'Wkrótce' },
  { id: 'later', label: 'Później' },
]

const monthShort = new Intl.DateTimeFormat('pl-PL', { month: 'short', timeZone: 'UTC' })

export function NextSteps({
  timeline,
  changedIds,
  changeVersion,
  hoveredId,
  onHover,
  onSelect,
}: {
  timeline: Timeline
  changedIds: Set<string>
  changeVersion: number
  hoveredId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}) {
  const groups = nextSteps(timeline)
  const year = timeline.today.slice(0, 4)
  if (GROUPS.every((group) => groups[group.id].length === 0)) return null
  return (
    <section aria-labelledby="next-steps" className="mt-6">
      <h3 id="next-steps" className="text-lg font-bold text-navy-900">
        Co przed Wami
      </h3>
      <div className="mt-2 space-y-4">
        {GROUPS.filter((group) => groups[group.id].length > 0).map((group) => (
          <div key={group.id} className="grid gap-1 sm:grid-cols-[96px_minmax(0,1fr)] sm:gap-4">
            <p
              className={cn(
                'pt-1 text-xs font-black tracking-wider uppercase sm:pt-5',
                group.id === 'now' ? 'text-zus-700' : 'text-navy-400',
              )}
            >
              {group.label}
            </p>
            <ul className="divide-y divide-line">
              {groups[group.id].map((step, index) => (
                <Row
                  key={step.key}
                  step={step}
                  index={index}
                  showYear={step.date.slice(0, 4) !== year}
                  changed={changedIds.has(step.id)}
                  changeVersion={changeVersion}
                  active={hoveredId === step.id}
                  onHover={onHover}
                  onSelect={onSelect}
                />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  )
}

function Row({
  step,
  index,
  showYear,
  changed,
  changeVersion,
  active,
  onHover,
  onSelect,
}: {
  step: Step
  index: number
  showYear: boolean
  changed: boolean
  changeVersion: number
  active: boolean
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}) {
  const date = new Date(`${step.date}T00:00:00Z`)
  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.04, ease: EASE_OUT }}
    >
      <button
        type="button"
        onClick={() => onSelect(step.id)}
        onMouseEnter={() => onHover(step.id)}
        onMouseLeave={() => onHover(null)}
        className={cn(
          'group flex w-full items-center gap-3 rounded-2xl px-2 py-2.5 text-left transition-colors duration-150 sm:gap-4',
          'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
          active ? 'bg-navy-50' : 'hover:bg-navy-50/60',
        )}
      >
        {/* A page from a wall calendar. */}
        <span
          className={cn(
            'relative grid w-12 shrink-0 overflow-hidden rounded-xl border bg-white text-center leading-none',
            step.overdue ? 'border-alert-600/40' : 'border-line',
          )}
        >
          <span
            className={cn(
              'py-1 text-[10px] font-black tracking-wide uppercase',
              step.overdue ? 'bg-alert-50 text-alert-600' : step.decide ? 'bg-zus-50 text-zus-700' : 'bg-navy-50 text-navy-500',
            )}
          >
            {monthShort.format(date).replace('.', '')}
          </span>
          <span className="pt-1 text-lg font-bold text-navy-900">{date.getUTCDate()}</span>
          <span className="pb-1 text-[10px] font-bold text-navy-400">{showYear ? step.date.slice(0, 4) : ' '}</span>
          {changed && <Pulse key={changeVersion} className="rounded-xl" />}
        </span>
        <Illustration src={step.icon} size="hint" />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="font-bold text-navy-900">{step.title}</span>
            {step.decide && (
              <span className="rounded-full bg-zus-50 px-2 py-0.5 text-[11px] font-bold text-zus-700">do wyboru</span>
            )}
          </span>
          <span className={cn('block text-sm', step.overdue ? 'font-bold text-alert-600' : 'text-navy-500')}>
            {step.detail}
          </span>
        </span>
        <ChevronRight className="size-4 shrink-0 text-navy-300 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-navy-500" />
      </button>
    </motion.li>
  )
}
