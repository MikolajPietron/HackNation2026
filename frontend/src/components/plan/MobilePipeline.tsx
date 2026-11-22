// The plan's timeline on a phone, as tracks: the desktop axis turned upright. Time runs down,
// months on the left; the mother's and the father's periods are columns side by side, so who is
// at home when, and for how long, reads at a glance like on the wide screen. Today is a navy
// line, the birth (or the due date) an amber one; the child's key days are icons in their own
// narrow track (a padlock on a point of no return). Deadlines years away (the end of parental
// leave in the year of the 6th birthday) sit behind a break in the scale, written out in full.
//
// A period shows as much as its height holds, in this order: its name, its length (and "do
// wyboru"), its dates and the monthly benefit from the engine; tapping it, or a day's icon, opens
// the details with the sources. Nothing is computed here: lengths, dates and amounts are the
// engine's, the scale only places them.
import { useLayoutEffect, useRef, useState } from 'react'
import { Lock } from 'lucide-react'
import dziecko from '@/assets/onboarding/dziecko.webp'
import mama from '@/assets/onboarding/mama.webp'
import tata from '@/assets/onboarding/tata.webp'
import { Pulse } from '@/components/timeline/Pulse'
import { dayNumber, formatDayMonthShort, formatShortDate, monthCells } from '@/lib/dates'
import { isKeyMarker, markerIcon, segmentIcon } from '@/lib/icons'
import { formatPlnShort, paymentFor } from '@/lib/money'
import { clipName, length } from '@/lib/plan'
import { remPx, textWidth, whenFontsReady } from '@/lib/textWidth'
import { cn } from '@/lib/utils'
import type { Marker, Segment, Timeline } from '@/types'

/** Days of margin before the first and after the last element. */
const PAD_DAYS = 6
/** A day this long after the last period goes behind the break. */
const FAR_AFTER_DAYS = 120
/** The height the scale aims at, and the bounds of pixels per day around it. */
const TARGET = 660
const MIN_PX_PER_DAY = 1
const MAX_PX_PER_DAY = 2.2
/** The shortest a period is drawn, so a fortnight stays a tappable bar with its length. */
const MIN_BAR = 22
const RULER = 42
const CHILD = 36
const GAP = 6
/** Padding inside a bar (px-2.5) on both sides. */
const BAR_PAD_X = 20
const ICON_GAP = 30

/** Green is the mother, navy the father; a dashed bar is still to decide. */
const BAR: Record<'mother' | 'father', Record<Segment['tone'], string>> = {
  mother: {
    leave: 'bg-zus-600 text-white',
    option: 'border-2 border-dashed border-zus-300 bg-white text-zus-900',
    work: 'bg-navy-100 text-navy-700',
  },
  father: {
    leave: 'bg-navy-700 text-white',
    option: 'border-2 border-dashed border-navy-300 bg-white text-navy-900',
    work: 'bg-navy-100 text-navy-700',
  },
}

const MONEY: Record<Segment['tone'], string> = {
  leave: 'bg-white/20 text-white',
  option: 'bg-sun-100 text-sun-700',
  work: 'bg-white text-navy-700',
}

/** The shortest word for a kind of period, for a narrow bar (as on the wide timeline). */
const TINY: [string, string][] = [
  ['sick', 'L4'],
  ['maternity', 'Macierzyński'],
  ['parental', 'Rodzicielski'],
  ['paternity', 'Ojcowski'],
  ['supplementary', 'Uzupełniający'],
  ['adoption', 'Urlop'],
  ['job-loss', 'Zasiłek'],
]

const tiny = (segment: Segment) =>
  TINY.find(([prefix]) => segment.id.startsWith(prefix))?.[1] ?? clipName(segment).split(' ')[0]

/** Names a bar can go by, longest first. */
function names(segment: Segment): string[] {
  const full = clipName(segment)
  const short = full.replace(/\s+(po porodzie|przed porodem)$/, '').replace(/^.*?:\s*/, '')
  return [...new Set([full, short.charAt(0).toUpperCase() + short.slice(1), tiny(segment)])]
}

interface BarText {
  name: string | null
  /** "18 tyg.", "32 tyg. · do wyboru" or the two in two lines; in a short bar the only line,
   *  with the kind when it fits ("Ojcowski · 14 dni"). */
  length: string[]
  dates: string | null
  money: string | null
  icon: boolean
}

const EMPTY: BarText = { name: null, length: [], dates: null, money: null, icon: false }

/** What a bar of this size can say, most important first, without cutting a word. */
function barText(timeline: Timeline, segment: Segment, width: number, height: number, scale: number): BarText {
  const room = width - BAR_PAD_X
  const option = segment.tone === 'option'
  const weeks = length(segment.days)
  const payment = paymentFor(timeline, segment.id)
  const money = payment ? `${formatPlnShort(payment.monthly)}/mies.` : null
  const dates = `${formatDayMonthShort(segment.start)} – ${formatDayMonthShort(segment.end)}`
  const line = (px: number) => px * 1.3 * scale
  const fits = (text: string, px: number) => textWidth(text, px * scale) <= room * 0.94

  let left = height - 10 * scale
  const take = (need: number) => {
    if (need > left) return false
    left -= need
    return true
  }

  // The name: the longest that fits in up to three lines.
  let name: string | null = null
  for (const candidate of names(segment)) {
    const lines = Math.ceil(textWidth(candidate, 13 * scale) / (room * 0.94))
    if (lines <= 3 && take(line(13) * lines)) {
      name = candidate
      break
    }
  }
  if (!name) {
    // A short bar, its text centred: the kind and the length in one line, or the length alone.
    const oneLine = `${tiny(segment)} · ${weeks}`
    if (height - 4 * scale < line(11)) return EMPTY
    if (fits(oneLine, 11)) return { ...EMPTY, length: [oneLine] }
    return { ...EMPTY, length: fits(weeks, 11) ? [weeks] : [] }
  }
  let lengthLines: string[] = []
  const together = `${weeks} · do wyboru`
  if (option && fits(together, 11) && take(line(11))) lengthLines = [together]
  else if (option && take(line(11) * 2)) lengthLines = [weeks, 'do wyboru']
  else if (take(line(11))) lengthLines = [weeks]
  const showMoney = Boolean(money) && fits(money ?? '', 11) && take(line(11) + 8 * scale)
  const showDates = fits(dates, 11) && take(line(11))
  const icon = take(ICON_GAP * scale)
  return {
    name,
    length: lengthLines,
    dates: showDates ? dates : null,
    money: showMoney ? money : null,
    icon,
  }
}

interface Placed {
  segment: Segment
  top: number
  height: number
  /** Which half of the column, when two periods of one parent overlap (rare). */
  half: 0 | 1 | null
}

/** Periods of one parent, top to bottom; a bar never hides the next one. */
function placeBars(segments: Segment[], y: (day: number) => number): Placed[] {
  const sorted = [...segments].sort((a, b) => dayNumber(a.start) - dayNumber(b.start))
  const placed: Placed[] = []
  let bottom = -Infinity
  let lastEnd = -Infinity
  for (const segment of sorted) {
    const start = dayNumber(segment.start)
    const end = dayNumber(segment.end) + 1
    const overlaps = start < lastEnd
    const top = overlaps ? y(start) : Math.max(y(start), bottom + 2)
    const height = Math.max(y(end) - top, MIN_BAR)
    if (overlaps && placed.length > 0) {
      placed[placed.length - 1].half = 0
      placed.push({ segment, top, height, half: 1 })
    } else {
      placed.push({ segment, top, height, half: null })
    }
    bottom = Math.max(bottom, top + height)
    lastEnd = Math.max(lastEnd, end)
  }
  return placed
}

interface Dot {
  marker: Marker
  /** Where the day is, and where its icon sits (pushed down when days are close). */
  at: number
  top: number
}

const DOT = 28

function placeDots(markers: Marker[], y: (day: number) => number): Dot[] {
  const sorted = [...markers].sort((a, b) => dayNumber(a.date) - dayNumber(b.date))
  const dots: Dot[] = []
  let next = -Infinity
  for (const marker of sorted) {
    const at = y(dayNumber(marker.date))
    const top = Math.max(at - DOT / 2, next)
    dots.push({ marker, at, top })
    next = top + DOT + 4
  }
  return dots
}

const locked = (marker: Marker) => marker.irreversible !== null && marker.irreversible.days_left >= 0

export function MobilePipeline({
  timeline,
  changedIds,
  changeVersion,
  selectedId,
  onSelect,
  preview = false,
  className,
}: {
  timeline: Timeline
  changedIds: Set<string>
  changeVersion: number
  selectedId: string | null
  onSelect: (id: string) => void
  /** A what-if is shown instead of the plan: the card says so with a dashed amber edge. */
  preview?: boolean
  className?: string
}) {
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [, setFontsReady] = useState(0)
  useLayoutEffect(() => {
    const element = box.current
    if (!element) return
    setWidth(element.clientWidth)
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(element)
    whenFontsReady(() => setFontsReady((n) => n + 1))
    return () => observer.disconnect()
  }, [])

  const today = dayNumber(timeline.today)
  const birth = dayNumber(timeline.birth_date)
  const mother = timeline.segments.filter((s) => s.lane === 'mother')
  const father = timeline.segments.filter((s) => s.lane === 'father')
  const periodDays = timeline.segments.flatMap((s) => [dayNumber(s.start), dayNumber(s.end) + 1])
  const lastPeriod = Math.max(today, birth, ...periodDays)
  const isFar = (day: number) => day > lastPeriod + FAR_AFTER_DAYS
  const markers = timeline.markers.filter((m) => !isFar(dayNumber(m.date)))
  const far = timeline.markers.filter((m) => isFar(dayNumber(m.date)))
  const near = [today, birth, ...periodDays, ...markers.map((m) => dayNumber(m.date))]
  const from = Math.min(...near) - PAD_DAYS
  const to = Math.max(...near) + PAD_DAYS
  const pxPerDay = Math.min(MAX_PX_PER_DAY, Math.max(MIN_PX_PER_DAY, TARGET / (to - from)))
  const y = (day: number) => (day - from) * pxPerDay
  const height = y(to)
  const months = monthCells(from, to).filter((m) => m.start >= from)
  const lastFar = far.length ? Math.max(...far.map((m) => dayNumber(m.date))) : to
  const farYears = Math.round((lastFar - to) / 365.25)

  const scale = remPx() / 16
  const column = Math.max(0, (width - RULER - CHILD - 3 * GAP) / 2)
  const motherBars = placeBars(mother, y)
  const fatherBars = placeBars(father, y)
  const dots = placeDots(markers, y)
  const inner = Math.max(height, ...[...motherBars, ...fatherBars].map((b) => b.top + b.height), ...dots.map((d) => d.top + DOT))
  const birthLabel = timeline.taken_in ? 'Przyjęcie' : timeline.child_born ? 'Poród' : 'Termin'
  const todayShown = today >= from && today <= to
  const birthShown = Math.abs(y(birth) - y(today)) >= 18 || !todayShown
  const pills = [...(todayShown ? [y(today)] : []), ...(birthShown ? [y(birth)] : [])]

  const left = { child: RULER + GAP, mother: RULER + CHILD + 2 * GAP, father: RULER + CHILD + 3 * GAP + column }

  return (
    <div
      className={cn(
        'rounded-4xl border px-3 pt-4 pb-4 transition-[border-color,background-color] duration-300',
        preview ? 'border-2 border-dashed border-sun-400 bg-sun-100/15' : 'border-line bg-white',
        className,
      )}
    >
      <div className="flex items-baseline justify-between gap-3 px-1">
        <h3 className="text-lg font-bold text-navy-900">Oś czasu</h3>
        <p className="text-xs font-bold text-navy-400">Stuknij okres albo ikonę</p>
      </div>

      <div ref={box} className="relative mt-3">
        {/* Track names: they stay on top while the long axis scrolls past. */}
        <div className="sticky top-0 z-30 -mx-1 flex items-end bg-white/95 px-1 pt-1 pb-2 backdrop-blur-sm">
          <span style={{ width: RULER }} />
          <span style={{ width: CHILD, marginLeft: GAP }} className="flex justify-center">
            <img src={dziecko} alt="" className="size-8 object-contain select-none" draggable={false} />
          </span>
          {[
            { label: 'Mama', image: mama, has: mother.length > 0 },
            { label: 'Tata', image: tata, has: father.length > 0 },
          ].map((lane) => (
            <span
              key={lane.label}
              style={{ width: column, marginLeft: GAP }}
              className={cn('flex items-center gap-1.5 pl-1', !lane.has && 'opacity-50')}
            >
              <img src={lane.image} alt="" className="size-8 object-contain select-none" draggable={false} />
              <span className="text-sm font-bold text-navy-900">{lane.label}</span>
            </span>
          ))}
        </div>

        {width > 0 && (
          <div className="relative" style={{ height: inner + 8 }}>
            {/* Tracks: a faint band for each, so the columns read as lanes. */}
            <span aria-hidden className="absolute inset-y-0 rounded-2xl bg-sun-100/35" style={{ left: left.child, width: CHILD }} />
            <span aria-hidden className="absolute inset-y-0 rounded-2xl bg-zus-50" style={{ left: left.mother, width: column }} />
            <span aria-hidden className="absolute inset-y-0 rounded-2xl bg-navy-50/70" style={{ left: left.father, width: column }} />

            {/* Months: a hairline at each first day, the name on the ruler (unless the name of
                today or of the birth stands there). */}
            {months.map((month, index) => {
              const top = y(month.start)
              const withYear = index === 0 || month.label.startsWith('sty')
              const covered = pills.some((pill) => top > pill - 14 && top < pill + (withYear ? 10 : 14))
              return (
                <div key={month.start} aria-hidden className="absolute inset-x-0" style={{ top }}>
                  <span className="absolute h-px bg-navy-100" style={{ left: RULER - 4, right: 0 }} />
                  {!covered && (
                    <span className="absolute -top-1.5 left-0 text-[11px] leading-none font-bold text-navy-500">
                      {month.label.replace('.', '')}
                      {withYear && <span className="mt-0.5 block text-[10px] font-bold text-navy-400">{month.year}</span>}
                    </span>
                  )}
                </div>
              )
            })}

            {/* Today runs behind the periods: it shows between the tracks and never crosses a
                period's text. */}
            {todayShown && (
              <span
                aria-hidden
                className="absolute z-5 h-0.5 rounded-full bg-navy-900"
                style={{ top: y(today) - 1, left: RULER - 4, right: 0 }}
              />
            )}

            {/* The birth, the day everything is counted from. */}
            <div aria-hidden className="absolute" style={{ top: y(birth), left: left.child, right: 0 }}>
              <span className="absolute inset-x-0 border-t-2 border-dashed border-sun-400" />
            </div>

            {[
              { bars: motherBars, x: left.mother },
              { bars: fatherBars, x: left.father },
            ].map(({ bars, x }) =>
              bars.map(({ segment, top, height: barHeight, half }) => {
                const parent = segment.lane === 'father' ? 'father' : 'mother'
                const barWidth = half === null ? column - 8 : (column - 10) / 2
                const text = barText(timeline, segment, barWidth, barHeight, scale)
                return (
                  <button
                    key={segment.id}
                    type="button"
                    onClick={() => onSelect(segment.id)}
                    aria-label={`${segment.title}, ${formatShortDate(segment.start)} – ${formatShortDate(segment.end)}, ${length(segment.days)}`}
                    style={{
                      top,
                      height: barHeight,
                      left: x + 4 + (half === 1 ? barWidth + 2 : 0),
                      width: barWidth,
                    }}
                    className={cn(
                      'absolute z-10 flex flex-col items-start overflow-hidden px-2.5 text-left',
                      'transition-[transform,box-shadow] duration-150 active:scale-[0.98]',
                      'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2 focus-visible:outline-none',
                      barHeight < 30 ? 'justify-center rounded-lg' : 'rounded-2xl py-1.25',
                      BAR[parent][segment.tone],
                      selectedId === segment.id && 'ring-2 ring-navy-900 ring-offset-2',
                    )}
                  >
                    {changedIds.has(segment.id) && (
                      <Pulse key={changeVersion} className={barHeight < 30 ? 'rounded-lg' : 'rounded-2xl'} />
                    )}
                    {text.icon && (
                      <span className="mb-1 grid size-7 shrink-0 place-items-center rounded-lg bg-white">
                        <img src={segmentIcon(segment)} alt="" className="size-6 object-contain select-none" draggable={false} />
                      </span>
                    )}
                    {text.name && <span className="text-[13px] leading-[1.3] font-bold text-pretty">{text.name}</span>}
                    {text.length.map((part) => (
                      <span key={part} className={cn('text-[11px] leading-[1.3] font-bold', text.name && 'opacity-80')}>
                        {part}
                      </span>
                    ))}
                    {text.dates && <span className="text-[11px] leading-[1.3] opacity-80">{text.dates}</span>}
                    {text.money && (
                      <span className={cn('mt-1 rounded-full px-1.5 py-px text-[11px] leading-[1.3] font-bold', MONEY[segment.tone])}>
                        {text.money}
                      </span>
                    )}
                  </button>
                )
              }),
            )}

            {/* The child's days: icons in their own track, pushed apart when close. */}
            {dots.map(({ marker, at, top }) => {
              const key = isKeyMarker(marker)
              return (
                <div key={marker.id}>
                  {top > at - DOT / 2 + 2 && (
                    <span
                      aria-hidden
                      className="absolute z-10 w-px bg-sun-400"
                      style={{ top: at, height: top + DOT / 2 - at, left: left.child + CHILD / 2 }}
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => onSelect(marker.id)}
                    aria-label={`${marker.title}, ${formatShortDate(marker.date)}`}
                    style={{ top, left: left.child + (CHILD - DOT) / 2, width: DOT, height: DOT }}
                    className={cn(
                      'absolute z-20 grid place-items-center rounded-full bg-white ring-1 transition-transform duration-150 active:scale-95',
                      'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                      key ? 'ring-sun-400' : 'ring-line',
                      selectedId === marker.id && 'ring-2 ring-navy-900',
                    )}
                  >
                    {changedIds.has(marker.id) && <Pulse key={changeVersion} />}
                    <img src={markerIcon(marker)} alt="" className="size-5 object-contain select-none" draggable={false} />
                    {locked(marker) && (
                      <span className="absolute -right-1 -bottom-1 grid size-3.5 place-items-center rounded-full bg-navy-900 text-white">
                        <Lock className="size-2" strokeWidth={3} />
                      </span>
                    )}
                  </button>
                </div>
              )
            })}

            {/* The names of today and of the birth, on the ruler. */}
            {todayShown && (
              <span
                aria-hidden
                className="pointer-events-none absolute left-0 z-20 -translate-y-1/2 rounded-full bg-navy-900 px-1.5 py-0.5 text-[10px] leading-none font-bold text-white"
                style={{ top: y(today) }}
              >
                Dziś
              </span>
            )}
            {birthShown && (
              <span
                aria-hidden
                className="pointer-events-none absolute left-0 z-20 -translate-y-1/2 rounded-full bg-sun-400 px-1.5 py-0.5 text-[10px] leading-none font-bold text-navy-900"
                style={{ top: y(birth) }}
              >
                {birthLabel}
              </span>
            )}
          </div>
        )}

        {far.length > 0 && (
          <>
            <div
              aria-hidden
              className="mt-2 flex h-8 items-center justify-center rounded-xl text-xs font-bold text-navy-400"
              style={{
                backgroundImage:
                  'repeating-linear-gradient(135deg, var(--color-navy-50) 0 6px, transparent 6px 12px)',
              }}
            >
              ⋯ {farYears > 0 ? `${farYears} ${farYears === 1 ? 'rok' : farYears < 5 ? 'lata' : 'lat'} później` : 'później'} ⋯
            </div>
            <ul className="mt-2 flex flex-col gap-2">
              {far.map((marker) => (
                <li key={marker.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(marker.id)}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-2xl border px-3 py-2 text-left transition-transform duration-150 active:scale-[0.98]',
                      'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                      isKeyMarker(marker) ? 'border-sun-300 bg-sun-100/50' : 'border-line bg-white',
                    )}
                  >
                    <img src={markerIcon(marker)} alt="" className="size-6 object-contain select-none" draggable={false} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-bold text-zus-700">{formatShortDate(marker.date)}</span>
                      <span className="block text-sm leading-snug font-bold text-navy-900">{marker.title}</span>
                    </span>
                    {locked(marker) && <Lock className="size-4 shrink-0 text-navy-700" />}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {/* What the shapes mean, once. */}
      <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 px-1 text-xs text-navy-500">
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-2.5 rounded-sm bg-zus-600" /> urlop mamy
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-2.5 rounded-sm bg-navy-700" /> urlop taty
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-2.5 rounded-sm border-2 border-dashed border-zus-300" /> do wyboru
        </li>
        <li className="flex items-center gap-1.5">
          <Lock className="size-3 text-navy-700" /> bez powrotu
        </li>
      </ul>
    </div>
  )
}
