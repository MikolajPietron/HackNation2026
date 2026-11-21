import { useEffect, useMemo, useRef } from 'react'
import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { ArrowRight, Check, FileText } from 'lucide-react'
import { dayNumber, formatDate, formatDayMonth, formatRange, monthCells } from '@/lib/dates'
import { EASE_OUT, SPRING_LAYOUT } from '@/lib/ease'
import { TONE } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { Document, Timeline } from '@/types'
import type { TimelineItem, TimelineViewProps } from './items'
import { Pulse } from './Pulse'

const TRACK_MIN_PX = 640
const ROW_PX = 58
const MARKER_ROW_PX = 28
const MARKER_LABEL_PX = 180 // room a marker label needs before the next one in the same row
const PAD_DAYS = 14 // empty days shown before the first and after the last element
const PAD_DAYS_ALONE = 75 // around a lone day (no periods), so the strip still shows a few months
const FULL_PILL_PERCENT = 26 // narrower pills keep only the initial; the title goes outside
const COMPACT_PILL_PERCENT = 8 // narrower still: an empty pill with everything outside
const MIN_MONTH_PERCENT = 3.5 // narrower month cells at the edges are not labelled
const FAR_DAYS = 60 // a marker this long after the last period is pinned to the right edge

// The birth marker sits on the start of the day, like the dashed birth line and the pills.
const BIRTH_MARKERS = new Set(['due-date', 'birth'])

type SegmentItem = Extract<TimelineItem, { kind: 'segment' }>
type MarkerItem = Extract<TimelineItem, { kind: 'marker' }>

/** Wide screens: a month strip and one rounded pill per period, like a schedule. */
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
  const { from, to, segments, documents, markers, farMarkers, markerRows, months } = plan

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
                    className={cn('text-[10px] leading-3.5', hasBirth ? 'text-white/85' : 'text-navy-500')}
                  >
                    {caption}
                  </span>
                </div>
              )
            })}
          </div>

          <div className="relative mt-1">
            <div className="pointer-events-none absolute inset-0" aria-hidden>
              <div
                className="absolute inset-y-0 border-l-2 border-dashed border-zus-300"
                style={{ left: `${x(birth)}%` }}
              />
              {within(today) && (
                <div
                  className="absolute inset-y-0 border-l border-navy-200"
                  style={{ left: `${x(today + 0.5)}%` }}
                />
              )}
            </div>

            <div
              className="relative"
              style={{ height: (markerRows + farMarkers.length) * MARKER_ROW_PX + 6 }}
            >
              {markers.map(({ item, row }) => (
                <MarkerChip
                  key={item.id}
                  ref={register(item.id)}
                  item={item}
                  left={x(item.startDay + (BIRTH_MARKERS.has(item.id) ? 0 : 0.5))}
                  top={row * MARKER_ROW_PX + 4}
                  selected={item.id === selectedId}
                  onClick={() => onSelect(item.id)}
                />
              ))}
              {farMarkers.map((item, index) => (
                <EdgeMarker
                  key={item.id}
                  ref={register(item.id)}
                  item={item}
                  top={(markerRows + index) * MARKER_ROW_PX + 4}
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
                  document={documents.get(item.id)}
                  selectedId={selectedId}
                  changedIds={changedIds}
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
        <Legend swatch={<span className="h-2.5 w-5 rounded-full bg-zus-600" />}>Urlop mamy</Legend>
        <Legend swatch={<span className="h-2.5 w-5 rounded-full bg-zus-200" />}>Do wyboru</Legend>
        <Legend swatch={<span className="h-2.5 w-5 rounded-full bg-navy-200" />}>Praca</Legend>
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
          Dokument
        </Legend>
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
  const flip = left > 70
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

/** A day years past the periods (a distant deadline): at the right edge, with its full date. */
function EdgeMarker({
  item,
  ref,
  top,
  selected,
  onClick,
}: {
  item: MarkerItem
  ref: (node: HTMLElement | null) => void
  top: number
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      title={`${item.title} — ${formatDate(item.start)}`}
      className={cn(
        'absolute right-0 flex h-5 items-center gap-1.5 text-[11px] font-bold whitespace-nowrap transition-colors',
        selected ? 'text-zus-700 underline underline-offset-2' : 'text-navy-700 hover:text-zus-700',
      )}
      style={{ top }}
    >
      {item.label} {formatDate(item.start)}
      <span className="size-2.5 shrink-0 rotate-45 rounded-[2px] bg-sun-400" />
      <ArrowRight className="size-3.5 text-navy-400" aria-hidden />
    </button>
  )
}

function PillRow({
  item,
  index,
  left,
  width,
  document,
  selectedId,
  changedIds,
  changeVersion,
  register,
  onSelect,
}: {
  item: SegmentItem
  index: number
  left: number
  width: number
  document: Document | undefined
  selectedId: string | null
  changedIds: Set<string>
  changeVersion: number
  register: (id: string) => (node: HTMLElement | null) => void
  onSelect: (id: string) => void
}) {
  const s = item.element
  const tone = TONE[s.tone]
  const size = width >= FULL_PILL_PERCENT ? 'full' : width >= COMPACT_PILL_PERCENT ? 'compact' : 'tiny'
  const top = index * ROW_PX + 7
  const duration = s.days % 7 === 0 ? `${s.days / 7} tyg.` : `${s.days} dni`
  const dates = `${formatDayMonth(s.start)} – ${formatDayMonth(s.end)}`
  const delay = index * 0.07
  // Each pill has its own row, so the label goes to whichever side has room.
  const labelOnLeft = left + width / 2 > 50

  return (
    <>
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
          tone.pill,
          item.id === selectedId && 'ring-2 ring-navy-900 ring-offset-2 ring-offset-canvas',
        )}
      >
        {changedIds.has(item.id) && <Pulse key={changeVersion} />}
        {size !== 'tiny' && (
          <span className="flex min-w-0 flex-1 items-center gap-2.5 overflow-hidden px-1.5">
            <span
              className={cn(
                'grid size-8 shrink-0 place-items-center rounded-full text-xs font-black',
                tone.avatar,
              )}
            >
              M
            </span>
            {size === 'full' && (
              <span className="min-w-0 flex-1 pr-3 text-left leading-tight">
                <span className="block truncate text-[13px] font-bold">{s.title}</span>
                <span className="block truncate text-[11px] opacity-80">
                  {dates} · {duration}
                </span>
              </span>
            )}
          </span>
        )}
      </motion.button>

      {size !== 'full' && (
        <button
          type="button"
          onClick={() => onSelect(item.id)}
          className={cn(
            'absolute flex h-11 flex-col justify-center text-xs leading-tight whitespace-nowrap',
            labelOnLeft ? 'items-end' : 'items-start',
          )}
          style={
            labelOnLeft
              ? { right: `calc(${100 - left}% + ${document ? 44 : 12}px)`, top }
              : { left: `calc(${left + width}% + 12px)`, top }
          }
        >
          <span className="font-bold text-navy-900">{s.title}</span>
          <span className="text-navy-500">
            {dates} · {duration}
          </span>
        </button>
      )}

      {document && (
        <button
          ref={register(document.id)}
          type="button"
          onClick={() => onSelect(document.id)}
          title={`${document.title} — potrzebne na ${formatDate(document.needed_by)}`}
          aria-label={`${document.title}, potrzebne na ${formatDate(document.needed_by)}`}
          className={cn(
            'absolute grid size-7 place-items-center rounded-full bg-white shadow-card ring-2 transition-transform duration-150 hover:scale-110',
            document.done ? 'text-zus-700 ring-zus-600' : 'text-sun-700 ring-sun-400',
            document.id === selectedId && 'ring-navy-900',
          )}
          style={{ left: `calc(${left}% - 36px)`, top: top + 8 }}
        >
          {changedIds.has(document.id) && <Pulse key={changeVersion} />}
          {document.done ? <Check className="size-3.5" /> : <FileText className="size-3.5" />}
        </button>
      )}
    </>
  )
}

/** Visible range, each pill's document and rows for marker labels. */
function layout(timeline: Timeline, items: TimelineItem[]) {
  const segments = items
    .filter((item): item is SegmentItem => item.kind === 'segment')
    .sort((a, b) => a.startDay - b.startDay)
  const allMarkers = items
    .filter((item): item is MarkerItem => item.kind === 'marker')
    .sort((a, b) => a.startDay - b.startDay)
  // A deadline years away would squeeze the periods into a sliver: it leaves the scale.
  // Without periods there is no scale to protect, so nothing is far.
  const lastPeriodEnd = segments.length > 0 ? Math.max(...segments.map((item) => item.endDay)) : Infinity
  const isFar = (item: TimelineItem) => item.kind === 'marker' && item.startDay > lastPeriodEnd + FAR_DAYS
  const farMarkers = allMarkers.filter(isFar)
  const days = items.filter((item) => !isFar(item)).flatMap((item) => [item.startDay, item.endDay])
  const pad = segments.length > 0 ? PAD_DAYS : PAD_DAYS_ALONE
  const from = Math.min(...days) - pad
  const to = Math.max(...days) + pad

  const documents = new Map<string, Document>()
  for (const document of timeline.documents) {
    if (document.segment_id) documents.set(document.segment_id, document)
  }

  const minGap = Math.ceil(((to - from) * MARKER_LABEL_PX) / TRACK_MIN_PX)
  const rowEnds: number[] = []
  const markers = allMarkers.filter((item) => !isFar(item)).map((item) => {
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
    documents,
    markers,
    farMarkers,
    markerRows: Math.max(rowEnds.length, 1),
    months,
  }
}
