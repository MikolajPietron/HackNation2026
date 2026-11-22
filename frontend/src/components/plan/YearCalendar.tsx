// The plan as a wall calendar. The question it answers at a glance: "when are we with the baby?".
// - compact (in the timeline card and on phones): every month of the leave, each day coloured
//   by who is at home (green the mother, navy the father; light when still to decide), important
//   days ringed in amber, today in navy. A hover says in a line what the day holds; a click opens
//   a card beside the day with everything on it (periods, important days, documents, money),
//   each line opening its details.
// - large ("Rozwiń"): months as on a paper wall calendar, the periods drawn as named bars across
//   the weeks, under each month the days worth writing down, and the chosen day in a panel.
// Everything is read from the engine's timeline (lib/day.ts); nothing is computed here.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, ReactNode, Ref } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronRight, Minimize2, X } from 'lucide-react'
import { Illustration } from '@/components/ui/illustration'
import { dayLines, monthAgenda } from '@/lib/day'
import type { AgendaItem, DayLine, DayTone } from '@/lib/day'
import { dayNumber, formatDistance, isoFromDay, monthCells } from '@/lib/dates'
import type { MonthCell } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { clipName } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { Segment, Timeline } from '@/types'

const WEEKDAYS = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd']
const monthName = new Intl.DateTimeFormat('pl-PL', { month: 'long', timeZone: 'UTC' })
const monthTitle = new Intl.DateTimeFormat('pl-PL', { month: 'long', year: 'numeric', timeZone: 'UTC' })
const weekdayDate = new Intl.DateTimeFormat('pl-PL', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})
const shortDay = new Intl.DateTimeFormat('pl-PL', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })
/** Months shown at most; the far deadlines are on the axis and in "Co przed Wami". */
const MAX_MONTHS = 18

type Fill = 'motherLeave' | 'motherOption' | 'fatherLeave' | 'fatherOption'

const COLOR: Record<Fill, string> = {
  motherLeave: 'var(--color-zus-600)',
  motherOption: 'var(--color-zus-100)',
  fatherLeave: 'var(--color-navy-700)',
  fatherOption: 'var(--color-navy-100)',
}

const LEGEND: { fill: Fill; label: string }[] = [
  { fill: 'motherLeave', label: 'Mama · urlop' },
  { fill: 'motherOption', label: 'Mama · do wyboru' },
  { fill: 'fatherLeave', label: 'Tata · urlop' },
  { fill: 'fatherOption', label: 'Tata · do wyboru' },
]

const fillOf = (s: Segment): Fill | null =>
  s.tone === 'work' ? null : (`${s.lane === 'father' ? 'father' : 'mother'}${s.tone === 'leave' ? 'Leave' : 'Option'}` as Fill)

/** Monday = 0. 1970-01-01 was a Thursday. */
const weekday = (day: number) => (((day + 3) % 7) + 7) % 7
const dateOf = (day: number) => new Date(`${isoFromDay(day)}T00:00:00Z`)

/** The colour of a line's dot in the day card. */
const DOT: Record<DayTone, string> = {
  mother: 'bg-zus-600',
  father: 'bg-navy-700',
  'option-mother': 'bg-zus-100 ring-1 ring-zus-400',
  'option-father': 'bg-navy-100 ring-1 ring-navy-300',
  work: 'bg-navy-200',
  event: 'bg-sun-400',
  document: 'bg-navy-400',
  money: 'bg-zus-300',
}

interface Facts {
  months: MonthCell[]
  fills: Map<number, Fill[]>
  /** Important days (amber) and days a document is due (navy). */
  events: Set<number>
  documents: Set<number>
}

function useFacts(timeline: Timeline, today: number): Facts {
  return useMemo(() => {
    const fills = new Map<number, Fill[]>()
    for (const s of timeline.segments) {
      const fill = fillOf(s)
      if (!fill) continue
      for (let day = dayNumber(s.start); day <= dayNumber(s.end); day += 1) {
        const list = fills.get(day) ?? []
        if (!list.includes(fill)) list.push(fill)
        fills.set(day, list)
      }
    }
    const events = new Set(timeline.markers.map((m) => dayNumber(m.date)))
    const documents = new Set<number>()
    for (const d of timeline.documents) {
      if (d.done) continue
      documents.add(dayNumber(d.needed_by))
      if (d.deadline) documents.add(dayNumber(d.deadline))
    }
    const periodDays = timeline.segments.flatMap((s) => [dayNumber(s.start), dayNumber(s.end)])
    const first = Math.min(today, dayNumber(timeline.birth_date), ...periodDays)
    const last = Math.max(today, dayNumber(timeline.birth_date), ...periodDays)
    return { months: monthCells(first, last).slice(0, MAX_MONTHS), fills, events, documents }
  }, [timeline, today])
}

export function YearCalendar({
  timeline,
  onSelect,
  size = 'compact',
  onCollapse,
  headerStart,
  onExpand,
}: {
  timeline: Timeline
  onSelect: (id: string) => void
  size?: 'compact' | 'large'
  /** Large: back to the card. */
  onCollapse?: () => void
  /** Compact: shown at the start of the toolbar (the view switch). */
  headerStart?: ReactNode
  /** Compact: open the large calendar. */
  onExpand?: () => void
}) {
  const today = dayNumber(timeline.today)
  const facts = useFacts(timeline, today)
  return size === 'large' ? (
    <LargeCalendar timeline={timeline} facts={facts} today={today} onSelect={onSelect} onCollapse={onCollapse} />
  ) : (
    <CompactCalendar
      timeline={timeline}
      facts={facts}
      today={today}
      onSelect={onSelect}
      headerStart={headerStart}
      onExpand={onExpand}
    />
  )
}

function Legend({ facts, className }: { facts: Facts; className?: string }) {
  const present = new Set([...facts.fills.values()].flat())
  return (
    <ul className={cn('flex flex-wrap gap-x-4 gap-y-1.5 text-xs font-bold text-navy-500', className)}>
      {LEGEND.filter((item) => present.has(item.fill)).map((item) => (
        <li key={item.fill} className="flex items-center gap-1.5">
          <span
            className={cn('size-3 rounded', item.fill.endsWith('Option') && 'border border-dashed border-navy-300')}
            style={{ background: COLOR[item.fill] }}
          />
          {item.label}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <span className="size-3 rounded ring-2 ring-sun-400 ring-inset" />
        ważny dzień
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-3 rounded ring-2 ring-navy-900 ring-inset" />
        dziś
      </li>
    </ul>
  )
}

// ---------------------------------------------------------------------------------------------
// Compact

interface Anchor {
  day: number
  /** Centre of the day, relative to the calendar box. */
  x: number
  top: number
  bottom: number
  /** Open above the day when there is no room below it on the screen. */
  above: boolean
}

function CompactCalendar({
  timeline,
  facts,
  today,
  onSelect,
  headerStart,
  onExpand,
}: {
  timeline: Timeline
  facts: Facts
  today: number
  onSelect: (id: string) => void
  headerStart?: ReactNode
  onExpand?: () => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const card = useRef<HTMLDivElement>(null)
  const [picked, setPicked] = useState<Anchor | null>(null)
  const [hover, setHover] = useState<Anchor | null>(null)
  const [width, setWidth] = useState(0)

  useLayoutEffect(() => {
    const element = box.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      setWidth(entry.contentRect.width)
      setPicked(null)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // The card closes on Escape and on a click anywhere else (a day opens its own card).
  useEffect(() => {
    if (!picked) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !document.querySelector('[aria-modal="true"]')) setPicked(null)
    }
    const onDown = (event: PointerEvent) => {
      const target = event.target as Element | null
      if (card.current?.contains(target) || target?.closest('[data-calendar-day]')) return
      setPicked(null)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerdown', onDown)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pointerdown', onDown)
    }
  }, [picked])

  const anchorOf = (day: number, element: HTMLElement): Anchor | null => {
    const outer = box.current?.getBoundingClientRect()
    if (!outer) return null
    const rect = element.getBoundingClientRect()
    return {
      day,
      x: rect.left - outer.left + rect.width / 2,
      top: rect.top - outer.top,
      bottom: rect.bottom - outer.top,
      above: rect.bottom + 300 > window.innerHeight && rect.top > 340,
    }
  }

  const cardWidth = Math.min(360, width)
  const left = (anchor: Anchor, w: number) => Math.min(Math.max(0, anchor.x - w / 2), Math.max(0, width - w))

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-3">
        {headerStart}
        <Legend facts={facts} className="min-w-0 flex-1" />
        {onExpand && (
          <button
            type="button"
            onClick={onExpand}
            aria-label="Rozwiń kalendarz"
            title="Rozwiń kalendarz"
            className="ml-auto grid h-9 min-w-9 place-items-center rounded-full px-2 text-navy-500 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.94] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
          >
            <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
            </svg>
          </button>
        )}
      </div>

      <div ref={box} className="relative">
        <div className="grid grid-cols-1 gap-x-6 gap-y-5 min-[420px]:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
          {facts.months.map((month) => {
            const blanks = weekday(month.start)
            const days = Array.from({ length: month.end - month.start + 1 }, (_, i) => month.start + i)
            const title = monthTitle.format(dateOf(month.start))
            return (
              <section key={month.start} aria-label={title}>
                <h4 className="mb-1.5 text-sm font-bold text-navy-900 first-letter:uppercase">{title}</h4>
                <div className="grid grid-cols-7 gap-0.5 text-center">
                  {WEEKDAYS.map((name) => (
                    <span key={name} className="pb-0.5 text-[10px] font-bold text-navy-400">
                      {name}
                    </span>
                  ))}
                  {Array.from({ length: blanks }, (_, i) => (
                    <span key={`b-${i}`} />
                  ))}
                  {days.map((day) => {
                    const list = facts.fills.get(day) ?? []
                    const solid = list.some((fill) => fill.endsWith('Leave'))
                    const style: CSSProperties =
                      list.length === 0
                        ? {}
                        : list.length === 1
                          ? { background: COLOR[list[0]] }
                          : { background: `linear-gradient(135deg, ${COLOR[list[0]]} 50%, ${COLOR[list[1]]} 50%)` }
                    const event = facts.events.has(day)
                    const document = facts.documents.has(day)
                    return (
                      <button
                        key={day}
                        type="button"
                        data-calendar-day
                        onClick={(e) => {
                          setHover(null)
                          setPicked(picked?.day === day ? null : anchorOf(day, e.currentTarget))
                        }}
                        onPointerEnter={(e) => e.pointerType === 'mouse' && setHover(anchorOf(day, e.currentTarget))}
                        onPointerLeave={() => setHover(null)}
                        aria-pressed={picked?.day === day}
                        aria-label={weekdayDate.format(dateOf(day))}
                        className={cn(
                          'relative grid aspect-square place-items-center rounded-md text-[11px] font-bold tabular-nums transition-transform duration-100 active:scale-90',
                          solid ? 'text-white' : list.length ? 'text-navy-900' : 'text-navy-500 hover:bg-navy-50',
                          event && 'ring-2 ring-sun-400 ring-inset',
                          day === today && 'ring-2 ring-navy-900 ring-inset',
                          picked?.day === day && 'outline-2 outline-offset-1 outline-navy-900',
                        )}
                        style={style}
                      >
                        {day - month.start + 1}
                        {document && !event && (
                          <span
                            aria-hidden
                            className={cn('absolute bottom-0.5 size-1 rounded-full', solid ? 'bg-white' : 'bg-navy-500')}
                          />
                        )}
                      </button>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </div>

        <AnimatePresence>
          {hover && hover.day !== picked?.day && width > 0 && (
            <motion.div
              key={`hover-${hover.day}`}
              initial={{ opacity: 0, y: 2 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, transition: { duration: 0.08 } }}
              transition={{ duration: 0.12, ease: EASE_OUT }}
              className="pointer-events-none absolute z-20 w-60 -translate-y-full rounded-2xl bg-navy-900 px-3 py-2 text-xs text-white shadow-[0_12px_30px_-12px_rgb(26_36_56/0.6)]"
              style={{ top: hover.top - 6, left: left(hover, Math.min(240, width)) }}
            >
              <HoverSummary timeline={timeline} day={hover.day} />
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {picked && width > 0 && (
            <motion.div
              key={picked.day}
              ref={card}
              role="dialog"
              aria-label={weekdayDate.format(dateOf(picked.day))}
              initial={{ opacity: 0, scale: 0.97, y: picked.above ? 6 : -6 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.12 } }}
              transition={{ duration: 0.2, ease: EASE_OUT }}
              className={cn(
                'absolute z-30 rounded-3xl border border-line bg-white p-4 shadow-[0_24px_60px_-24px_rgb(26_36_56/0.45)]',
                picked.above ? 'origin-bottom -translate-y-full' : 'origin-top',
              )}
              style={{
                width: cardWidth,
                left: left(picked, cardWidth),
                top: picked.above ? picked.top - 8 : picked.bottom + 8,
              }}
            >
              <DayCard
                timeline={timeline}
                day={picked.day}
                onSelect={(id) => {
                  setPicked(null)
                  onSelect(id)
                }}
                onClose={() => setPicked(null)}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <p className="mt-4 text-xs font-bold text-navy-400">Kliknij dzień, żeby zobaczyć, co się wtedy dzieje.</p>
    </div>
  )
}

/** One line per thing on the day, for the hover tooltip. */
function HoverSummary({ timeline, day }: { timeline: Timeline; day: number }) {
  const lines = dayLines(timeline, day).filter((line) => line.tone !== 'money')
  return (
    <>
      <p className="font-bold first-letter:uppercase">{shortDay.format(dateOf(day)).replace('.', '')}</p>
      {lines.length === 0 ? (
        <p className="mt-0.5 text-white/70">Nic się nie dzieje</p>
      ) : (
        <ul className="mt-1 space-y-0.5">
          {lines.slice(0, 4).map((line) => (
            <li key={line.key} className="flex items-start gap-1.5">
              <span className={cn('mt-1 size-2 shrink-0 rounded-full', DOT[line.tone])} />
              <span>{line.tone === 'event' || line.tone === 'document' ? line.title : `${line.lead} · ${line.title}`}</span>
            </li>
          ))}
          {lines.length > 4 && <li className="text-white/60">i {lines.length - 4} więcej — kliknij</li>}
        </ul>
      )}
    </>
  )
}

/** Everything on one day, each line opening its details. */
function DayCard({
  timeline,
  day,
  onSelect,
  onClose,
  onHover,
}: {
  timeline: Timeline
  day: number
  onSelect: (id: string) => void
  onClose?: () => void
  onHover?: (id: string | null) => void
}) {
  const lines = dayLines(timeline, day)
  const label = weekdayDate.format(dateOf(day))
  const comma = label.indexOf(', ')
  return (
    <div aria-live="polite">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-navy-500 capitalize">{label.slice(0, comma)}</p>
          <p className="mt-0.5 text-lg leading-tight font-bold text-navy-900">{label.slice(comma + 2)}</p>
          <p className="mt-0.5 text-sm text-navy-500">{formatDistance(timeline.today, isoFromDay(day))}</p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Zamknij"
            className="-mt-1 -mr-1 grid size-8 shrink-0 place-items-center rounded-full text-navy-400 transition-colors hover:bg-navy-50 hover:text-navy-900"
          >
            <X className="size-4" />
          </button>
        )}
      </div>
      {lines.length === 0 ? (
        <p className="mt-3 text-sm text-navy-500">Tego dnia w Waszym planie nic się nie dzieje.</p>
      ) : (
        <ul className="-mx-2 mt-3 space-y-0.5">
          {lines.map((line) => (
            <DayLineRow key={line.key} line={line} onSelect={onSelect} onHover={onHover} />
          ))}
        </ul>
      )}
    </div>
  )
}

function DayLineRow({
  line,
  onSelect,
  onHover,
}: {
  line: DayLine
  onSelect: (id: string) => void
  onHover?: (id: string | null) => void
}) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(line.id)}
        onMouseEnter={() => onHover?.(line.id)}
        onMouseLeave={() => onHover?.(null)}
        className="group flex w-full items-start gap-2.5 rounded-2xl px-2 py-1.5 text-left transition-colors duration-150 hover:bg-navy-50"
      >
        <Illustration src={line.icon} size="hint" />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5 text-[11px] font-bold tracking-wide text-navy-500 uppercase">
            <span className={cn('size-2 shrink-0 rounded-full', DOT[line.tone])} />
            {line.lead}
          </span>
          <span className="block text-sm leading-snug font-bold text-navy-900">{line.title}</span>
          <span className="block text-sm leading-snug text-navy-500">{line.rest}</span>
        </span>
        <ChevronRight className="mt-1 size-4 shrink-0 text-navy-300 transition-transform group-hover:translate-x-0.5 group-hover:text-navy-500" />
      </button>
    </li>
  )
}

// ---------------------------------------------------------------------------------------------
// Large

/** The nearest ancestor that scrolls (the window the large calendar opens in). */
function scrollParent(element: HTMLElement | null): HTMLElement | null {
  for (let node = element?.parentElement ?? null; node; node = node.parentElement) {
    const { overflowY } = window.getComputedStyle(node)
    if (overflowY === 'auto' || overflowY === 'scroll') return node
  }
  return null
}

interface Piece {
  segment: Segment
  /** Columns of the week, Monday = 0. */
  from: number
  to: number
  roundStart: boolean
  roundEnd: boolean
}

/** The periods of one week of a month as bars, mother's rows above the father's. */
function weekBars(timeline: Timeline, weekStart: number, month: MonthCell): Piece[][] {
  const first = Math.max(weekStart, month.start)
  const last = Math.min(weekStart + 6, month.end)
  const pieces: Piece[] = []
  for (const s of timeline.segments) {
    if (s.tone === 'work') continue
    const start = dayNumber(s.start)
    const end = dayNumber(s.end)
    const from = Math.max(start, first)
    const to = Math.min(end, last)
    if (from > to) continue
    pieces.push({ segment: s, from: from - weekStart, to: to - weekStart, roundStart: from === start, roundEnd: to === end })
  }
  const laneOrder = (p: Piece) => (p.segment.lane === 'father' ? 1 : 0)
  pieces.sort((a, b) => laneOrder(a) - laneOrder(b) || a.from - b.from)
  const rows: { lane: number; last: number; pieces: Piece[] }[] = []
  for (const piece of pieces) {
    const row = rows.find((r) => r.lane === laneOrder(piece) && r.last < piece.from)
    if (row) {
      row.pieces.push(piece)
      row.last = piece.to
    } else rows.push({ lane: laneOrder(piece), last: piece.to, pieces: [piece] })
  }
  return rows.map((r) => r.pieces)
}

const BAR: Record<Fill, string> = {
  motherLeave: 'bg-zus-600 text-white',
  motherOption: 'border border-dashed border-zus-400 bg-zus-50 text-zus-900',
  fatherLeave: 'bg-navy-700 text-white',
  fatherOption: 'border border-dashed border-navy-300 bg-navy-50 text-navy-900',
}

const CHIP: Record<AgendaItem['tone'], string> = {
  event: 'bg-sun-100 text-sun-700',
  document: 'bg-navy-50 text-navy-700',
  start: 'bg-zus-50 text-zus-700',
  option: 'bg-zus-50 text-zus-700',
  end: 'bg-navy-50 text-navy-500',
}

function LargeCalendar({
  timeline,
  facts,
  today,
  onSelect,
  onCollapse,
}: {
  timeline: Timeline
  facts: Facts
  today: number
  onSelect: (id: string) => void
  onCollapse?: () => void
}) {
  const [picked, setPicked] = useState(today)
  const [lit, setLit] = useState<number | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const header = useRef<HTMLElement>(null)
  const current = useRef<HTMLElement>(null)

  // Open at the month of today, not at the first month of the plan: once the window has come
  // in (its entrance scales it), under the header that stays on top.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const scroller = scrollParent(root.current)
      const target = current.current
      if (!scroller || !target) return
      const offset = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top
      const top = scroller.scrollTop + offset - (header.current?.offsetHeight ?? 0) - 16
      if (top > 160) scroller.scrollTo({ top })
    }, 320)
    return () => window.clearTimeout(timer)
  }, [])

  return (
    <div ref={root} className="@container">
      <header
        ref={header}
        className="sticky top-0 z-20 -mx-6 mb-6 flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-line bg-white px-6 pt-2 pb-4"
      >
        <h2 className="text-2xl font-bold tracking-tight text-navy-900">Kalendarz</h2>
        <Legend facts={facts} className="min-w-0 flex-1 text-sm" />
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            className="flex h-10 items-center gap-2 rounded-full px-4 text-sm font-bold text-navy-700 transition-colors hover:bg-navy-50"
          >
            <Minimize2 className="size-4" /> Zwiń
          </button>
        )}
      </header>

      <div className="grid gap-8 @4xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid gap-x-12 gap-y-12" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 400px), 1fr))' }}>
          {facts.months.map((month) => (
            <LargeMonth
              key={month.start}
              ref={month.start <= today && today <= month.end ? current : undefined}
              timeline={timeline}
              facts={facts}
              month={month}
              today={today}
              picked={picked}
              lit={lit}
              onPick={setPicked}
              onLight={setLit}
              onSelect={onSelect}
            />
          ))}
        </div>

        <aside className="@4xl:sticky @4xl:top-24 @4xl:self-start">
          <div className="rounded-3xl bg-navy-50/70 p-5">
            <DayCard timeline={timeline} day={picked} onSelect={onSelect} />
          </div>
          <p className="mt-3 px-1 text-xs font-bold text-navy-400">
            Kliknij dzień w kalendarzu, żeby zobaczyć, co się wtedy dzieje.
          </p>
        </aside>
      </div>
    </div>
  )
}

function LargeMonth({
  ref,
  timeline,
  facts,
  month,
  today,
  picked,
  lit,
  onPick,
  onLight,
  onSelect,
}: {
  ref?: Ref<HTMLElement>
  timeline: Timeline
  facts: Facts
  month: MonthCell
  today: number
  picked: number
  lit: number | null
  onPick: (day: number) => void
  onLight: (day: number | null) => void
  onSelect: (id: string) => void
}) {
  const weeks = useMemo(() => {
    const list: number[] = []
    for (let start = month.start - weekday(month.start); start <= month.end; start += 7) list.push(start)
    return list
  }, [month])
  const agenda = useMemo(() => monthAgenda(timeline, month.start, month.end), [timeline, month])
  const date = dateOf(month.start)

  return (
    <section ref={ref} aria-label={monthTitle.format(date)}>
      <h3 className="mb-3 flex items-baseline gap-2 text-xl font-bold text-navy-900">
        <span className="first-letter:uppercase">{monthName.format(date)}</span>
        <span className="text-base text-navy-400">{date.getUTCFullYear()}</span>
      </h3>
      <div className="grid grid-cols-7 border-b border-line pb-1.5">
        {WEEKDAYS.map((name, i) => (
          <span key={name} className={cn('px-1.5 text-xs font-bold', i >= 5 ? 'text-navy-300' : 'text-navy-400')}>
            {name}
          </span>
        ))}
      </div>
      {weeks.map((weekStart) => {
        const rows = weekBars(timeline, weekStart, month)
        const height = Math.max(1, rows.length)
        return (
          <div
            key={weekStart}
            className="grid grid-cols-7 border-b border-line/70"
            style={{ gridTemplateRows: `34px repeat(${height}, 22px) 8px` }}
          >
            {Array.from({ length: 7 }, (_, i) => {
              const day = weekStart + i
              if (day < month.start || day > month.end) {
                return <span key={day} style={{ gridColumn: i + 1, gridRow: `1 / span ${height + 2}` }} />
              }
              const event = facts.events.has(day)
              const document = facts.documents.has(day)
              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => onPick(day)}
                  aria-pressed={picked === day}
                  aria-label={weekdayDate.format(dateOf(day))}
                  style={{ gridColumn: i + 1, gridRow: `1 / span ${height + 2}` }}
                  className={cn(
                    'relative flex items-start justify-between rounded-xl px-1.5 pt-1.5 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                    picked === day ? 'bg-navy-50 ring-2 ring-navy-900 ring-inset' : lit === day ? 'bg-sun-100/60' : 'hover:bg-navy-50/70',
                  )}
                >
                  <span
                    className={cn(
                      'grid size-6 place-items-center rounded-full text-[13px] font-bold tabular-nums',
                      day === today
                        ? 'bg-navy-900 text-white'
                        : event
                          ? 'bg-sun-100 text-sun-700 ring-2 ring-sun-400'
                          : i >= 5
                            ? 'text-navy-400'
                            : 'text-navy-900',
                    )}
                  >
                    {day - month.start + 1}
                  </span>
                  {document && <span aria-hidden className="mt-1.5 mr-0.5 size-1.5 rounded-full bg-navy-500" />}
                </button>
              )
            })}
            {rows.map((row, r) =>
              row.map((piece) => {
                const fill = fillOf(piece.segment)!
                const span = piece.to - piece.from + 1
                return (
                  <span
                    key={`${piece.segment.id}-${weekStart}`}
                    aria-hidden
                    className={cn(
                      'pointer-events-none z-10 mx-0.5 truncate px-2 text-[11px] leading-[20px] font-bold',
                      BAR[fill],
                      piece.roundStart ? 'rounded-l-full' : 'rounded-l-sm -ml-px',
                      piece.roundEnd ? 'rounded-r-full' : 'rounded-r-sm -mr-px',
                    )}
                    style={{ gridColumn: `${piece.from + 1} / ${piece.to + 2}`, gridRow: r + 2, height: 20 }}
                  >
                    {span >= 2 || piece.roundStart ? clipName(piece.segment) : ''}
                  </span>
                )
              }),
            )}
          </div>
        )
      })}

      {agenda.length > 0 && (
        <ul className="mt-3 space-y-0.5">
          {agenda.map((item) => (
            <li key={item.key}>
              <button
                type="button"
                onClick={() => {
                  onPick(item.day)
                  onSelect(item.id)
                }}
                onMouseEnter={() => onLight(item.day)}
                onMouseLeave={() => onLight(null)}
                className="group flex w-full items-start gap-2.5 rounded-xl px-1.5 py-1 text-left transition-colors hover:bg-navy-50"
              >
                <span className={cn('w-9 shrink-0 rounded-lg py-0.5 text-center text-xs font-black tabular-nums', CHIP[item.tone])}>
                  {item.day - month.start + 1}
                </span>
                <Illustration src={item.icon} size="hint" />
                <span className="min-w-0 flex-1 text-sm leading-snug font-bold text-pretty text-navy-900">{item.title}</span>
                <ChevronRight className="size-4 shrink-0 text-navy-300 opacity-0 transition-opacity group-hover:opacity-100" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
