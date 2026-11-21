import { Fragment, useEffect, useMemo, useRef } from 'react'
import type { ReactNode } from 'react'
import { dayNumber, durationLabel, formatDate, formatLongDate, formatRange } from '@/lib/dates'
import { formatPercent, LANE, LANE_ORDER } from '@/lib/ui'
import { cn } from '@/lib/utils'
import { ElementDetails } from './ElementDetails'
import type { TimelineItem, TimelineViewProps } from './items'

/** Phones and narrow columns: one chronological list; tap an item to open its details. */
export function VerticalTimeline({
  timeline,
  items,
  selectedId,
  changedIds,
  changeVersion,
  focus,
  onSelect,
}: TimelineViewProps) {
  const refs = useRef(new Map<string, HTMLElement>())
  const sorted = useMemo(
    () =>
      [...items].sort(
        (a, b) => a.startDay - b.startDay || LANE_ORDER[a.lane] - LANE_ORDER[b.lane],
      ),
    [items],
  )
  const today = dayNumber(timeline.today)
  const todayIndex = sorted.findIndex((item) => item.startDay > today)

  useEffect(() => {
    if (focus.id) refs.current.get(focus.id)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [focus.id, focus.tick])

  return (
    <ol className="relative ml-2 space-y-3 border-l-2 border-line pl-5">
      {sorted.map((item, index) => {
        const isSelected = item.id === selectedId
        const changed = changedIds.has(item.id)
        const passed = item.kind === 'application' && item.element.passed
        const example = item.kind === 'segment' && item.element.is_example
        return (
          <Fragment key={item.id}>
            {index === todayIndex && <TodayRow date={timeline.today} />}
            <li
              ref={(node) => {
                if (node) refs.current.set(item.id, node)
                else refs.current.delete(item.id)
              }}
              className="relative scroll-mt-24"
            >
              <span
                className={cn(
                  'absolute top-5 -left-[29px] size-4 border-[3px] border-canvas',
                  item.kind === 'segment' ? 'rounded-full' : 'rounded-[4px]',
                  item.kind === 'marker' && 'rotate-45',
                  passed ? 'bg-alert-600' : LANE[item.lane].dot,
                )}
              />
              <button
                key={changed ? `${item.id}:${changeVersion}` : item.id}
                type="button"
                onClick={() => onSelect(isSelected ? null : item.id)}
                aria-expanded={isSelected}
                className={cn(
                  'w-full rounded-3xl bg-white p-4 text-left shadow-card transition',
                  isSelected && 'ring-2 ring-navy-900',
                  changed && 'motion-safe:animate-pop',
                )}
              >
                <p className="text-xs font-bold text-navy-500">{dateText(item)}</p>
                <p className="mt-0.5 font-black text-navy-900">{item.title}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Chip className={LANE[item.lane].chip}>
                    {item.kind === 'application'
                      ? `Wniosek · ${item.element.parent === 'mother' ? 'mama' : 'tata'}`
                      : LANE[item.lane].label}
                  </Chip>
                  {item.kind === 'segment' && (
                    <Chip className="bg-navy-50 text-navy-700 ring-navy-100">
                      {formatPercent(item.element.rate_percent)} · {durationLabel(item.element.days)}
                    </Chip>
                  )}
                  {example && (
                    <Chip className="bg-white text-navy-500 ring-navy-200">przykładowy termin</Chip>
                  )}
                  {passed && (
                    <Chip className="bg-alert-50 text-alert-600 ring-alert-600/30">termin minął</Chip>
                  )}
                </div>
              </button>
              {isSelected && (
                <div className="mt-2 rounded-3xl bg-white p-5 shadow-card motion-safe:animate-msg-in">
                  <ElementDetails item={item} timeline={timeline} onSelect={onSelect} />
                </div>
              )}
            </li>
          </Fragment>
        )
      })}
    </ol>
  )
}

function dateText(item: TimelineItem): string {
  switch (item.kind) {
    case 'segment':
      return formatRange(item.element.start, item.element.end)
    case 'marker':
      return formatLongDate(item.element.date)
    case 'application':
      return item.element.is_deadline
        ? `Termin: do ${formatDate(item.element.due)}`
        : `Potrzebny na: ${formatDate(item.element.due)}`
  }
}

function TodayRow({ date }: { date: string }) {
  return (
    <li className="relative flex items-center gap-2 py-1">
      <span className="absolute -left-[27px] size-3 rounded-full bg-zus-600 ring-4 ring-zus-100" />
      <span className="rounded-full bg-zus-600 px-2.5 py-0.5 text-xs font-bold text-white">
        Dziś · {formatDate(date)}
      </span>
    </li>
  )
}

function Chip({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-bold ring-1', className)}>
      {children}
    </span>
  )
}
