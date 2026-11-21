import { useEffect, useMemo, useRef } from 'react'
import { dayNumber, formatDate, formatRange, monthTicks } from '../../lib/dates'
import { cx, formatPercent, LANE, LANES } from '../../lib/ui'
import type { Timeline } from '../../types'
import { ElementDetails } from './ElementDetails'
import type { TimelineItem, TimelineViewProps } from './items'

const TRACK_MIN_PX = 880
const LABEL_PX = 150 // room a point label needs before the next one in the same row
const SEGMENT_ROW = 52
const POINT_ROW = 46
const NARROW_BAR_PERCENT = 9 // below this width the bar's text goes next to it
const EDGE_PERCENT = 11 // point labels closer to an edge than this are not centred

/** Desktop: lanes left to right on a month axis. */
export function HorizontalTimeline({
  timeline,
  items,
  selectedId,
  changedIds,
  changeVersion,
  focus,
  onSelect,
}: TimelineViewProps) {
  const refs = useRef(new Map<string, HTMLElement>())
  const { from, to, lanes, later, ticks } = useMemo(() => layout(timeline, items), [timeline, items])
  const selected = items.find((item) => item.id === selectedId) ?? null

  useEffect(() => {
    if (focus.id) {
      refs.current.get(focus.id)?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
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
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white shadow-sm">
        <div className="relative" style={{ minWidth: TRACK_MIN_PX }}>
          <div className="flex border-b border-stone-200">
            <div className="sticky left-0 z-20 w-28 shrink-0 border-r border-stone-100 bg-white" />
            <div className="relative h-9 flex-1">
              {ticks.map((tick) => (
                <span
                  key={tick.day}
                  className="absolute top-2.5 pl-1.5 text-[11px] whitespace-nowrap text-stone-500"
                  style={{ left: `${x(tick.day)}%` }}
                >
                  {tick.year === null ? (
                    tick.label
                  ) : (
                    <span className="font-semibold text-stone-800">{tick.year}</span>
                  )}
                </span>
              ))}
              {within(today) && (
                <span
                  className="absolute top-2 z-10 -translate-x-1/2 rounded-full bg-teal-600 px-2 py-0.5 text-[10px] font-semibold text-white"
                  style={{ left: `${x(today + 0.5)}%` }}
                >
                  Dziś
                </span>
              )}
            </div>
          </div>

          <div className="relative">
            <div className="pointer-events-none absolute inset-y-0 right-0 left-28">
              {ticks.map((tick) => (
                <div
                  key={tick.day}
                  className="absolute inset-y-0 border-l border-stone-100"
                  style={{ left: `${x(tick.day)}%` }}
                />
              ))}
              {within(birth) && (
                <div
                  className="absolute inset-y-0 border-l-2 border-dashed border-amber-300"
                  style={{ left: `${x(birth)}%` }}
                />
              )}
              {within(today) && (
                <div
                  className="absolute inset-y-0 border-l-2 border-teal-500/70"
                  style={{ left: `${x(today + 0.5)}%` }}
                />
              )}
            </div>

            {lanes.map(({ lane, placed, rows, rowHeight }) => (
              <div key={lane} className="flex border-b border-stone-100 last:border-b-0">
                <div className="sticky left-0 z-20 flex w-28 shrink-0 items-start gap-2 border-r border-stone-100 bg-white px-3 py-3.5 text-sm font-medium text-stone-700">
                  <span className={cx('mt-1.5 size-2 shrink-0 rounded-full', LANE[lane].dot)} />
                  {LANE[lane].label}
                </div>
                <div className="relative flex-1" style={{ height: rows * rowHeight + 12 }}>
                  {placed.map(({ item, row }) => {
                    const changed = changedIds.has(item.id)
                    const common = {
                      ref: register(item.id),
                      onClick: () => onSelect(item.id),
                      isSelected: item.id === selectedId,
                      changed,
                    }
                    return item.kind === 'segment' ? (
                      <SegmentBar
                        key={changed ? `${item.id}:${changeVersion}` : item.id}
                        {...common}
                        item={item}
                        left={x(item.startDay)}
                        width={x(item.endDay + 1) - x(item.startDay)}
                        top={row * rowHeight + 6}
                      />
                    ) : (
                      <PointMarker
                        key={changed ? `${item.id}:${changeVersion}` : item.id}
                        {...common}
                        item={item}
                        left={x(item.startDay + 0.5)}
                        top={row * rowHeight + 8}
                      />
                    )
                  })}
                </div>
              </div>
            ))}
          </div>

          {later.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-t border-stone-200 px-3 py-2.5 text-xs text-stone-600">
              <span className="font-medium">Dalej na osi:</span>
              {later.map((item) => (
                <button
                  key={item.id}
                  ref={register(item.id)}
                  type="button"
                  onClick={() => onSelect(item.id)}
                  className={cx(
                    'rounded-full px-2.5 py-1 font-medium ring-1 transition',
                    item.id === selectedId
                      ? 'bg-stone-900 text-white ring-stone-900'
                      : 'bg-amber-50 text-amber-900 ring-amber-200 hover:bg-amber-100',
                  )}
                >
                  {item.label} · {formatDate(item.start)}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
        {selected ? (
          <ElementDetails item={selected} timeline={timeline} onSelect={onSelect} />
        ) : (
          <p className="text-sm text-stone-500">
            Kliknij element osi, żeby zobaczyć zasady, wnioski i źródła z cytatami.
          </p>
        )}
      </div>
    </div>
  )
}

interface MarkProps {
  ref: (node: HTMLElement | null) => void
  onClick: () => void
  isSelected: boolean
  changed: boolean
  left: number
  top: number
}

function SegmentBar({
  item,
  ref,
  onClick,
  isSelected,
  changed,
  left,
  width,
  top,
}: MarkProps & { item: Extract<TimelineItem, { kind: 'segment' }>; width: number }) {
  const s = item.element
  const narrow = width < NARROW_BAR_PERCENT
  const duration = s.days % 7 === 0 ? `${s.days / 7} tyg.` : `${s.days} dni`
  const meta = `${formatPercent(s.rate_percent)} · ${duration}`
  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={onClick}
        title={`${s.title}: ${formatRange(s.start, s.end)}`}
        className={cx(
          'absolute flex h-10 min-w-2 flex-col justify-center overflow-hidden rounded-lg border px-2 text-left text-xs shadow-sm transition hover:brightness-95',
          LANE[s.lane].bar,
          s.is_example && 'border-dashed',
          isSelected && 'ring-2 ring-stone-900 ring-offset-2',
          changed && 'motion-safe:animate-flash',
        )}
        style={{ left: `${left}%`, width: `${width}%`, top }}
      >
        {!narrow && (
          <>
            <span className="truncate font-semibold">{s.title}</span>
            <span className="truncate opacity-80">{meta}</span>
          </>
        )}
      </button>
      {narrow && (
        <button
          type="button"
          onClick={onClick}
          className="absolute flex h-10 flex-col justify-center text-left text-xs whitespace-nowrap"
          style={{ left: `calc(${left + width}% + 6px)`, top }}
        >
          <span className="font-semibold text-stone-800">{s.title}</span>
          <span className="text-stone-500">{meta}</span>
        </button>
      )}
    </>
  )
}

function PointMarker({
  item,
  ref,
  onClick,
  isSelected,
  changed,
  left,
  top,
}: MarkProps & { item: Exclude<TimelineItem, { kind: 'segment' }> }) {
  const passed = item.kind === 'application' && item.element.passed
  const align = left < EDGE_PERCENT ? 'start' : left > 100 - EDGE_PERCENT ? 'end' : 'center'
  const shift = {
    start: 'translateX(-6px)',
    center: 'translateX(-50%)',
    end: 'translateX(calc(-100% + 6px))',
  }
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      title={`${item.title} — ${formatDate(item.start)}`}
      className={cx(
        'group absolute flex flex-col gap-1 rounded-md',
        { start: 'items-start', center: 'items-center', end: 'items-end' }[align],
        changed && 'motion-safe:animate-flash',
      )}
      style={{ left: `${left}%`, top, transform: shift[align] }}
    >
      <span
        className={cx(
          'size-3 ring-2 ring-white',
          item.kind === 'marker' ? 'rotate-45 rounded-[3px]' : 'rounded-sm',
          passed ? 'bg-red-500' : LANE[item.lane].dot,
        )}
      />
      <span
        className={cx(
          'max-w-40 truncate rounded-md px-1.5 py-0.5 text-[11px] font-medium shadow-sm ring-1',
          isSelected
            ? 'bg-stone-900 text-white ring-stone-900'
            : passed
              ? 'bg-red-50 text-red-800 ring-red-200'
              : 'bg-white text-stone-700 ring-stone-200 group-hover:bg-stone-50',
        )}
      >
        {item.label}
      </span>
    </button>
  )
}

/** Visible range, rows per lane (so bars and labels do not overlap) and far-away items. */
function layout(timeline: Timeline, items: TimelineItem[]) {
  const segments = items.filter((item) => item.kind === 'segment')
  const from = Math.min(dayNumber(timeline.birth_date), ...segments.map((s) => s.startDay)) - 14
  const to = Math.max(...segments.map((s) => s.endDay)) + 28
  const minGap = Math.ceil(((to - from) * LABEL_PX) / TRACK_MIN_PX)
  const visible = items.filter((item) => item.startDay >= from && item.startDay <= to)
  const later = items.filter((item) => item.startDay < from || item.startDay > to)

  const lanes = LANES.map((lane) => {
    const rowEnds: number[] = []
    const placed = visible
      .filter((item) => item.lane === lane)
      .sort((a, b) => a.startDay - b.startDay)
      .map((item) => {
        const end = item.kind === 'segment' ? item.endDay + 1 : item.startDay + minGap
        let row = rowEnds.findIndex((rowEnd) => rowEnd <= item.startDay)
        if (row === -1) row = rowEnds.push(end) - 1
        else rowEnds[row] = end
        return { item, row }
      })
    const isPoints = lane === 'child' || lane === 'applications'
    return { lane, placed, rows: Math.max(rowEnds.length, 1), rowHeight: isPoints ? POINT_ROW : SEGMENT_ROW }
  })

  return { from, to, lanes, later, ticks: monthTicks(from, to) }
}
