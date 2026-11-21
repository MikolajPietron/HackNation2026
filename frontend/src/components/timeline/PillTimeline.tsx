import { useEffect, useMemo, useRef } from 'react'
import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { FileText } from 'lucide-react'
import { dayNumber, formatDate, formatDayMonth, formatRange, monthCells } from '@/lib/dates'
import { EASE_OUT, SPRING_LAYOUT } from '@/lib/ease'
import { formatPercent, LANE, LANE_ORDER } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { Application, Timeline } from '@/types'
import type { TimelineItem, TimelineViewProps } from './items'

const TRACK_MIN_PX = 640
const ROW_PX = 58
const MARKER_ROW_PX = 28
const MARKER_LABEL_PX = 180 // room a marker label needs before the next one in the same row
const PAD_BEFORE_DAYS = 30
const PAD_AFTER_DAYS = 21
const FULL_PILL_PERCENT = 24 // narrower pills keep the initial and the rate, the title goes outside
const MIN_MONTH_PERCENT = 3.5 // narrower month cells at the edges are not labelled
const COMPACT_PILL_PERCENT = 12 // narrower still: an empty pill with everything outside

type SegmentItem = Extract<TimelineItem, { kind: 'segment' }>
type MarkerItem = Extract<TimelineItem, { kind: 'marker' }>

/** Wide screens: a month strip and one rounded pill per leave, cascading down like a schedule. */
export function PillTimeline({
  timeline,
  items,
  selectedId,
  changedIds,
  changeVersion,
  focus,
  onSelect,
}: TimelineViewProps) {
  const refs = useRef(new Map<string, HTMLElement>())
  const plan = useMemo(() => layout(timeline, items), [timeline, items])
  const { from, to, segments, deadlines, markers, markerRows, later, months } = plan

  useEffect(() => {
    if (focus.id) {
      refs.current
        .get(focus.id)
        ?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    }
  }, [focus.id, focus.tick])

  const x = (day: number) => ((day - from) / (to - from)) * 100
  const within = (day: number) => day >= from && day <= to
  const today = dayNumber(timeline.today)
  const birth = dayNumber(timeline.birth_date)
  const register = (id: string) => (node: HTMLElement | null) => {
    if (node) refs.current.set(id, node)
    else refs.current.delete(id)
  }

  return (
    <div className="space-y-3">
      <div className="-mx-3 overflow-x-auto px-3 py-2">
        <div style={{ minWidth: TRACK_MIN_PX }}>
          <div className="relative h-14">
            {months.map((month) => {
              const hasBirth = birth >= month.start && birth <= month.end
              const hasToday = today >= month.start && today <= month.end
              const caption = hasBirth
                ? timeline.child_born
                  ? 'poród'
                  : 'termin'
                : hasToday
                  ? 'dziś'
                  : month.newYear
                    ? String(month.year)
                    : ' '
              return (
                <div
                  key={month.start}
                  className={cn(
                    'absolute inset-y-1 flex flex-col items-center justify-center rounded-2xl',
                    hasBirth
                      ? 'bg-zus-600 text-white shadow-pill'
                      : hasToday
                        ? 'bg-white text-navy-900 shadow-card'
                        : 'text-navy-700',
                  )}
                  style={{ left: `calc(${month.left}% + 2px)`, width: `calc(${month.width}% - 4px)` }}
                >
                  <span className="text-sm leading-4 font-black">{month.label}</span>
                  <span
                    className={cn(
                      'text-[10px] leading-3.5',
                      hasBirth ? 'text-white/85' : 'text-navy-500',
                    )}
                  >
                    {caption}
                  </span>
                </div>
              )
            })}
          </div>

          <div className="relative mt-1">
            <div className="pointer-events-none absolute inset-0" aria-hidden>
              {within(birth) && (
                <div
                  className="absolute inset-y-0 border-l-2 border-dashed border-zus-300"
                  style={{ left: `${x(birth)}%` }}
                />
              )}
              {within(today) && (
                <div
                  className="absolute inset-y-0 border-l border-navy-200"
                  style={{ left: `${x(today + 0.5)}%` }}
                />
              )}
            </div>

            <div className="relative" style={{ height: markerRows * MARKER_ROW_PX + 6 }}>
              {markers.map(({ item, row }) => (
                <MarkerChip
                  key={item.id}
                  ref={register(item.id)}
                  item={item}
                  left={x(item.startDay + 0.5)}
                  top={row * MARKER_ROW_PX + 4}
                  selected={item.id === selectedId}
                  onClick={() => onSelect(item.id)}
                />
              ))}
            </div>

            <div className="relative" style={{ height: segments.length * ROW_PX }}>
              {segments.map((item, index) => (
                <PillRow
                  key={item.id}
                  item={item}
                  index={index}
                  left={x(item.startDay)}
                  width={x(item.endDay + 1) - x(item.startDay)}
                  deadline={deadlines.get(item.id)}
                  deadlineLeft={
                    deadlines.has(item.id)
                      ? x(dayNumber(deadlines.get(item.id)!.due) + 0.5)
                      : null
                  }
                  selectedId={selectedId}
                  changed={changedIds.has(item.id)}
                  changeVersion={changeVersion}
                  register={register}
                  onSelect={onSelect}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-3xl bg-white px-5 py-3 text-xs text-navy-700 shadow-card">
        <Legend swatch={<span className="size-2 rounded-full bg-zus-600" />}>Mama</Legend>
        <Legend swatch={<span className="size-2 rounded-full bg-navy-700" />}>Tata</Legend>
        <Legend swatch={<span className="h-2.5 w-5 rounded-full bg-zus-200" />}>
          Przykładowy termin
        </Legend>
        <Legend swatch={<span className="size-2 rotate-45 rounded-[2px] bg-sun-400" />}>
          Ważny dzień
        </Legend>
        <Legend
          swatch={
            <span className="grid size-4 place-items-center rounded-full text-sun-700 ring-2 ring-sun-400">
              <FileText className="size-2.5" />
            </span>
          }
        >
          Termin wniosku
        </Legend>
        {later.map((item) => (
          <button
            key={item.id}
            ref={register(item.id)}
            type="button"
            onClick={() => onSelect(item.id)}
            className={cn(
              'ml-auto rounded-full px-3 py-1 font-bold transition-colors',
              item.id === selectedId
                ? 'bg-navy-900 text-white'
                : 'bg-sun-100 text-sun-700 hover:bg-sun-300',
            )}
          >
            {item.label} · {formatDate(item.start)}
          </button>
        ))}
      </div>
    </div>
  )
}

function Legend({ swatch, children }: { swatch: ReactNode; children: ReactNode }) {
  return (
    <span className="flex items-center gap-2">
      {swatch}
      {children}
    </span>
  )
}

function MarkerChip({
  item,
  ref,
  left,
  top,
  selected,
  onClick,
}: {
  item: MarkerItem
  ref: (node: HTMLElement | null) => void
  left: number
  top: number
  selected: boolean
  onClick: () => void
}) {
  // The diamond sits on the exact day; the label runs right, or left near the right edge.
  const flip = left > 78
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      title={`${item.title} — ${formatDate(item.start)}`}
      className={cn(
        'absolute flex h-5 items-center gap-1.5 rounded-full text-[11px] font-bold whitespace-nowrap transition-colors',
        flip && 'flex-row-reverse',
        selected ? 'text-zus-700 underline underline-offset-2' : 'text-navy-700 hover:text-zus-700',
      )}
      style={{
        left: `${left}%`,
        top,
        transform: flip ? 'translateX(calc(-100% + 5px))' : 'translateX(-5px)',
      }}
    >
      <span className="size-2.5 shrink-0 rotate-45 rounded-[2px] bg-sun-400" />
      {item.label} · {formatDayMonth(item.start)}
    </button>
  )
}

function PillRow({
  item,
  index,
  left,
  width,
  deadline,
  deadlineLeft,
  selectedId,
  changed,
  changeVersion,
  register,
  onSelect,
}: {
  item: SegmentItem
  index: number
  left: number
  width: number
  deadline: Application | undefined
  deadlineLeft: number | null
  selectedId: string | null
  changed: boolean
  changeVersion: number
  register: (id: string) => (node: HTMLElement | null) => void
  onSelect: (id: string) => void
}) {
  const s = item.element
  const lane = LANE[s.lane]
  const size = width >= FULL_PILL_PERCENT ? 'full' : width >= COMPACT_PILL_PERCENT ? 'compact' : 'tiny'
  const top = index * ROW_PX + 7
  const duration = s.days % 7 === 0 ? `${s.days / 7} tyg.` : `${s.days} dni`
  const rate = formatPercent(s.rate_percent)
  const labelOnLeft = left + width / 2 > 60
  const delay = index * 0.07

  return (
    <>
      {deadlineLeft !== null && deadlineLeft < left && (
        <span
          aria-hidden
          className="absolute border-t-2 border-dotted border-sun-300"
          style={{ left: `${deadlineLeft}%`, width: `${left - deadlineLeft}%`, top: top + 21 }}
        />
      )}

      <motion.button
        ref={register(item.id)}
        type="button"
        onClick={() => onSelect(item.id)}
        title={`${s.title}: ${formatRange(s.start, s.end)}`}
        initial={{ opacity: 0, x: -16, left: `${left}%`, width: `${width}%` }}
        animate={{ opacity: 1, x: 0, left: `${left}%`, width: `${width}%` }}
        transition={{
          ...SPRING_LAYOUT,
          opacity: { duration: 0.35, delay, ease: EASE_OUT },
          x: { duration: 0.45, delay, ease: EASE_OUT },
        }}
        style={{ top }}
        className={cn(
          'absolute flex h-11 min-w-3 items-center rounded-full shadow-pill',
          s.is_example ? lane.soft : lane.solid,
          item.id === selectedId && 'ring-2 ring-navy-900 ring-offset-2 ring-offset-canvas',
        )}
      >
        {changed && (
          <motion.span
            key={changeVersion}
            aria-hidden
            className="pointer-events-none absolute inset-0 rounded-full ring-4 ring-sun-400"
            initial={{ opacity: 1, scale: 1 }}
            animate={{ opacity: 0, scale: 1.05 }}
            transition={{ duration: 1.6, ease: EASE_OUT }}
          />
        )}
        {size !== 'tiny' && (
          <span className="flex min-w-0 flex-1 items-center justify-between gap-2 overflow-hidden px-1.5">
            <span
              className={cn(
                'grid size-8 shrink-0 place-items-center rounded-full text-xs font-black',
                s.is_example ? 'bg-white' : 'bg-white/20',
              )}
            >
              {lane.initial}
            </span>
            {size === 'full' && (
              <span className="min-w-0 flex-1 text-left leading-tight">
                <span className="block truncate text-[13px] font-bold">{s.title}</span>
                <span className="block truncate text-[11px] opacity-80">
                  {lane.label} · {duration}
                </span>
              </span>
            )}
            <span
              className={cn(
                'grid h-8 min-w-8 shrink-0 place-items-center rounded-full bg-white px-1.5 text-[10px] font-black',
                lane.text,
              )}
            >
              {rate}
            </span>
          </span>
        )}
      </motion.button>

      {size !== 'full' && (
        <button
          type="button"
          onClick={() => onSelect(item.id)}
          className={cn(
            'absolute flex h-11 flex-col justify-center text-xs leading-tight whitespace-nowrap',
            labelOnLeft && 'items-end',
          )}
          style={
            labelOnLeft
              ? { right: `calc(${100 - Math.min(left, deadlineLeft ?? left)}% + 20px)`, top }
              : { left: `calc(${left + width}% + 10px)`, top }
          }
        >
          <span className="font-bold text-navy-900">{s.title}</span>
          <span className="text-navy-500">
            {size === 'tiny' ? `${rate} · ${duration}` : duration}
          </span>
        </button>
      )}

      {deadline && deadlineLeft !== null && (
        <button
          ref={register(deadline.id)}
          type="button"
          onClick={() => onSelect(deadline.id)}
          title={`${deadline.title} — termin: ${formatDate(deadline.due)}`}
          aria-label={`${deadline.title}, termin ${formatDate(deadline.due)}`}
          className={cn(
            'absolute grid size-7 -translate-x-1/2 place-items-center rounded-full bg-white shadow-card ring-2 transition-transform duration-150 hover:scale-110',
            deadline.passed ? 'text-alert-600 ring-alert-600' : 'text-sun-700 ring-sun-400',
            deadline.id === selectedId && 'ring-navy-900',
          )}
          style={{ left: `${deadlineLeft}%`, top: top + 8 }}
        >
          <FileText className="size-3.5" />
        </button>
      )}
    </>
  )
}

/** Visible range, pill order, each leave's application deadline and rows for marker labels. */
function layout(timeline: Timeline, items: TimelineItem[]) {
  const segments = items
    .filter((item): item is SegmentItem => item.kind === 'segment')
    .sort((a, b) => a.startDay - b.startDay || LANE_ORDER[a.lane] - LANE_ORDER[b.lane])
  const from =
    Math.min(dayNumber(timeline.birth_date), ...segments.map((s) => s.startDay)) - PAD_BEFORE_DAYS
  const to = Math.max(...segments.map((s) => s.endDay)) + PAD_AFTER_DAYS
  const within = (day: number) => day >= from && day <= to

  const deadlines = new Map<string, Application>()
  for (const application of timeline.applications) {
    if (application.is_deadline && application.segment_id && within(dayNumber(application.due))) {
      deadlines.set(application.segment_id, application)
    }
  }

  const allMarkers = items.filter((item): item is MarkerItem => item.kind === 'marker')
  const minGap = Math.ceil(((to - from) * MARKER_LABEL_PX) / TRACK_MIN_PX)
  const rowEnds: number[] = []
  const markers = allMarkers
    .filter((item) => within(item.startDay))
    .sort((a, b) => a.startDay - b.startDay)
    .map((item) => {
      let row = rowEnds.findIndex((end) => end <= item.startDay)
      if (row === -1) row = rowEnds.push(item.startDay + minGap) - 1
      else rowEnds[row] = item.startDay + minGap
      return { item, row }
    })

  // Month cells clipped to the range; slivers at the edges are dropped. The year is
  // written under the first cell and under every January.
  const months = monthCells(from, to)
    .map((month) => {
      const start = Math.max(month.start, from)
      const end = Math.min(month.end + 1, to)
      return {
        ...month,
        left: ((start - from) / (to - from)) * 100,
        width: ((end - start) / (to - from)) * 100,
      }
    })
    .filter((month) => month.width >= MIN_MONTH_PERCENT)
    .map((month, index, all) => ({
      ...month,
      newYear: index === 0 || all[index - 1].year !== month.year,
    }))

  return {
    from,
    to,
    segments,
    deadlines,
    markers,
    markerRows: Math.max(rowEnds.length, 1),
    later: allMarkers.filter((item) => !within(item.startDay)),
    months,
  }
}
