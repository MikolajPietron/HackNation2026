// FUNKCJE F4 "Kalendarz wypłat": what comes in each calendar month and who pays it, straight
// from the engine (Timeline.monthly, ZADANIA B.12). The front adds nothing up and divides
// nothing: every amount on screen is one the engine gave. A month is the money for its days, not
// the day it reaches the account (the engine's assumption, in "Dlaczego tak?").
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { ChevronRight } from 'lucide-react'
import { addDaysIso } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { formatPln, formatPlnShort, formatRate } from '@/lib/money'
import { periodName } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { MonthlyLine, MonthlyPayment, Payment, Timeline } from '@/types'

const WHO = { mother: 'Mama', father: 'Tata' } as const
const BARS_HEIGHT = 136
/** A run of this many months without money or more folds into one narrow column. */
const LONG_GAP = 3

/** Solid when the period is set, light when it is still to decide; green mother, navy father. */
const FILL = {
  mother: { leave: 'var(--color-zus-600)', option: 'var(--color-zus-300)' },
  father: { leave: 'var(--color-navy-700)', option: 'var(--color-navy-300)' },
} as const

/** Money handed over by the employer (its own sick pay, or the benefit it pays as the payer). */
const fromEmployer = (line: MonthlyLine) => line.payer === 'employer' || line.payer === 'payer'

const monthLong = new Intl.DateTimeFormat('pl-PL', { month: 'long', year: 'numeric', timeZone: 'UTC' })
const monthShort = new Intl.DateTimeFormat('pl-PL', { month: 'short', timeZone: 'UTC' })
const asDate = (month: string) => new Date(`${month}-01T00:00:00Z`)
/** "2027-03" -> "marzec 2027" */
const monthName = (month: string) => monthLong.format(asDate(month))
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)
const lower = (text: string) => text.charAt(0).toLowerCase() + text.slice(1)
/** "2027-03" -> "mar" */
const monthLabel = (month: string) => monthShort.format(asDate(month)).replace('.', '')

type Column =
  | { kind: 'month'; key: string; month: MonthlyPayment }
  /** Months in a row without a paid day (a break between parts of the leave). */
  | { kind: 'gap'; key: string; months: MonthlyPayment[] }

function columnsOf(monthly: MonthlyPayment[]): Column[] {
  const columns: Column[] = []
  let run: MonthlyPayment[] = []
  const flush = () => {
    if (run.length >= LONG_GAP) columns.push({ kind: 'gap', key: `gap-${run[0].month}`, months: run })
    else for (const month of run) columns.push({ kind: 'month', key: month.month, month })
    run = []
  }
  for (const month of monthly) {
    if (month.total === 0) {
      run.push(month)
      continue
    }
    flush()
    columns.push({ kind: 'month', key: month.month, month })
  }
  flush()
  return columns
}

export function MonthChart({
  timeline,
  hoveredId,
  onSelect,
}: {
  timeline: Timeline
  /** A payment hovered elsewhere on the card: its months stay bright, the rest fade. */
  hoveredId: string | null
  /** Open a period's details. */
  onSelect: (paymentId: string) => void
}) {
  const reduce = useReducedMotion()
  const box = useRef<HTMLDivElement>(null)
  const buttons = useRef<(HTMLButtonElement | null)[]>([])
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const element = box.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const columns = useMemo(() => columnsOf(timeline.monthly), [timeline.monthly])
  const payments = useMemo(() => new Map(timeline.payments.map((p) => [p.id, p])), [timeline.payments])
  const option = (id: string) => {
    const payment = payments.get(id)
    return timeline.segments.find((s) => s.id === payment?.segment_id)?.tone === 'option'
  }
  // A line is light only when all its periods are still to decide.
  const light = (line: MonthlyLine) => line.payment_ids.every(option)

  // The dips: a period that pays a lower rate than the one right before it, for the same parent.
  const dips = useMemo(() => {
    const found = new Map<string, number>()
    const list = [...timeline.payments].sort((a, b) => a.start.localeCompare(b.start))
    for (const p of list) {
      const before = list.find((q) => q.lane === p.lane && addDaysIso(q.end, 1) === p.start)
      if (before && p.rate < before.rate) found.set(p.start.slice(0, 7), p.rate)
    }
    return found
  }, [timeline.payments])

  const thisMonth = timeline.today.slice(0, 7)
  // The month shown under the chart: the one picked, else this month, else the next with money.
  const [picked, setPicked] = useState<string | null>(null)
  const index = (() => {
    const found = columns.findIndex((c) => c.key === picked)
    if (found >= 0) return found
    const now = columns.findIndex((c) => c.kind === 'month' && c.month.month === thisMonth)
    if (now >= 0) return now
    const next = columns.findIndex((c) => c.kind === 'month' && c.month.month > thisMonth)
    return next >= 0 ? next : 0
  })()
  const shown = columns[index]
  const setSelected = (i: number) => setPicked(columns[i]?.key ?? null)

  // The scale only: the biggest month. Its amount is the one guide line on the chart.
  const top = Math.max(1, ...timeline.monthly.map((m) => m.total))
  const height = (amount: number) => (amount / top) * BARS_HEIGHT

  const step = columns.length === 0 ? 1 : width / columns.length >= 34 ? 1 : width / columns.length >= 18 ? 2 : 3
  const employerLines = timeline.monthly.flatMap((m) => m.lines).filter(fromEmployer)
  const anyLight = timeline.monthly.some((m) => m.lines.some(light))
  const parents = (['mother', 'father'] as const).filter((p) => timeline.monthly.some((m) => m[p] > 0))

  const move = (event: KeyboardEvent, from: number) => {
    const to =
      event.key === 'ArrowRight' ? from + 1 : event.key === 'ArrowLeft' ? from - 1 : event.key === 'Home' ? 0 : event.key === 'End' ? columns.length - 1 : null
    if (to === null || to < 0 || to >= columns.length) return
    event.preventDefault()
    setSelected(to)
    buttons.current[to]?.focus()
  }

  if (columns.length === 0) return null
  return (
    <div className="mt-4">
      <div ref={box} className="scrollbar-soft overflow-x-auto">
        <div className="relative" style={{ minWidth: columns.length * 12 }}>
        {/* The guide line: the biggest month's amount. */}
        <div className="pointer-events-none absolute inset-x-0" style={{ top: 20 }} aria-hidden>
          <div className="border-t border-dashed border-navy-200" />
          <span className="absolute -top-4 left-0 text-[10px] font-bold text-navy-400 tabular-nums">
            {formatPlnShort(top)}
          </span>
        </div>
        <div
          role="group"
          aria-label="Wypłaty miesiąc po miesiącu. Strzałki w lewo i w prawo zmieniają miesiąc."
          className="relative flex items-end gap-[3px] pt-5"
          style={{ height: BARS_HEIGHT + 20 }}
        >
          {columns.map((column, i) => {
            const active = i === index
            const faded =
              hoveredId !== null && (column.kind === 'gap' || !column.month.payment_ids.includes(hoveredId))
            const common = {
              ref: (element: HTMLButtonElement | null) => {
                buttons.current[i] = element
              },
              type: 'button' as const,
              tabIndex: active ? 0 : -1,
              onMouseEnter: () => setSelected(i),
              onFocus: () => setSelected(i),
              onClick: () => setSelected(i),
              onKeyDown: (event: KeyboardEvent) => move(event, i),
              'aria-pressed': active,
            }
            if (column.kind === 'gap') {
              return (
                <button
                  key={column.key}
                  {...common}
                  aria-label={`${monthName(column.months[0].month)} – ${monthName(column.months[column.months.length - 1].month)}: bez wypłat`}
                  className={cn(
                    'relative flex h-full w-4 shrink-0 items-end justify-center rounded-md transition-colors',
                    active ? 'bg-navy-50' : 'hover:bg-navy-50/60',
                  )}
                >
                  <span className="mb-1 text-xs font-black text-navy-300">⋯</span>
                </button>
              )
            }
            const month = column.month
            const dip = dips.get(month.month)
            const bar = height(month.total)
            return (
              <button
                key={column.key}
                {...common}
                aria-label={describe(month)}
                className={cn(
                  'relative flex h-full min-w-2.25 flex-1 flex-col items-stretch justify-end rounded-md transition-[background-color,opacity] duration-150',
                  active ? 'bg-navy-50' : 'hover:bg-navy-50/60',
                  faded && 'opacity-35',
                )}
              >
                {dip !== undefined && (
                  <span
                    className="pointer-events-none absolute left-1/2 -translate-x-1/2 text-[10px] font-black whitespace-nowrap text-navy-500 tabular-nums"
                    style={{ bottom: bar + 3 }}
                    aria-hidden
                  >
                    ↓{width / columns.length >= 30 ? ` ${formatRate(dip)}` : ''}
                  </span>
                )}
                {month.total === 0 ? (
                  <span className="mx-0.5 mb-px border-t-2 border-dashed border-navy-200" aria-hidden />
                ) : (
                  <motion.span
                    className="mx-0.5 flex flex-col-reverse gap-px overflow-hidden rounded-t-[5px] rounded-b-[2px]"
                    initial={false}
                    animate={{ height: bar }}
                    transition={reduce ? { duration: 0 } : { duration: 0.45, ease: EASE_OUT }}
                    aria-hidden
                  >
                    {month.lines.map((line) => (
                      <span
                        key={`${line.parent}-${line.payer}`}
                        className="min-h-px"
                        style={{
                          flexGrow: line.amount,
                          background: fromEmployer(line)
                            ? stripes(FILL[line.parent][light(line) ? 'option' : 'leave'])
                            : FILL[line.parent][light(line) ? 'option' : 'leave'],
                        }}
                      />
                    ))}
                  </motion.span>
                )}
              </button>
            )
          })}
        </div>
        {/* Month names under the bars; January and the first month carry the year. */}
        <div className="mt-1 flex gap-[3px]" aria-hidden>
          {columns.map((column, i) => {
            if (column.kind === 'gap') return <span key={column.key} className="w-4 shrink-0" />
            const month = column.month.month
            const now = month === thisMonth
            // Every `step`-th month is named, but never right next to a month that must be.
            const label =
              forced(columns, i, thisMonth) ||
              (i % step === 0 && (step === 1 || (!forced(columns, i - 1, thisMonth) && !forced(columns, i + 1, thisMonth))))
            return (
              <span
                key={column.key}
                className={cn(
                  'flex min-w-2.25 flex-1 flex-col text-[10px] leading-tight whitespace-nowrap',
                  // The edge labels stay inside the card (a flex item overflows away from its end).
                  i === 0 ? 'items-start' : i === columns.length - 1 ? 'items-end' : 'items-center',
                  now ? 'font-black text-navy-900' : 'font-bold text-navy-400',
                )}
              >
                {label && (
                  <>
                    {now ? 'dziś' : monthLabel(month)}
                    {(month.endsWith('-01') || i === 0) && (
                      <span className="block font-normal text-navy-300">{month.slice(2, 4)}</span>
                    )}
                  </>
                )}
              </span>
            )
          })}
        </div>
        </div>
      </div>

      {shown && <MonthDetail column={shown} payments={payments} timeline={timeline} light={light} onSelect={onSelect} />}

      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs font-bold text-navy-500">
        {parents.map((parent) => (
          <li key={parent} className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: FILL[parent].leave }} />
            {WHO[parent]}
          </li>
        ))}
        {anyLight && (
          <li className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: FILL.mother.option }} />
            jaśniej: do wyboru
          </li>
        )}
        {employerLines.length > 0 && (
          <li className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: stripes(FILL.mother.leave) }} />
            w paski: wypłaca {employerWord(employerLines)}
          </li>
        )}
        {dips.size > 0 && <li>↓ niższa stawka</li>}
      </ul>
    </div>
  )
}

/** The month under the chart: how much, for whom, for which period and who pays it. */
function MonthDetail({
  column,
  payments,
  timeline,
  light,
  onSelect,
}: {
  column: Column
  payments: Map<string, Payment>
  timeline: Timeline
  light: (line: MonthlyLine) => boolean
  onSelect: (paymentId: string) => void
}) {
  if (column.kind === 'gap') {
    const first = column.months[0].month
    const last = column.months[column.months.length - 1].month
    return (
      <div className="mt-3 rounded-2xl bg-navy-50/60 px-4 py-3 text-sm" aria-live="polite">
        <p className="font-bold text-navy-900">
          {capital(monthName(first))} – {monthName(last)}
        </p>
        <p className="mt-0.5 text-navy-500">Bez wypłat przez {column.months.length} mies.</p>
      </div>
    )
  }
  const month = column.month
  const periods = (line: MonthlyLine) =>
    [
      ...new Set(
        line.payment_ids.map((id) => {
          const payment = payments.get(id)
          const segment = timeline.segments.find((s) => s.id === payment?.segment_id)
          return segment ? periodName(segment) : (payment?.title ?? '')
        }),
      ),
    ].join(', ')
  return (
    <div className="mt-3 rounded-2xl bg-navy-50/60 px-2 py-2 text-sm" aria-live="polite">
      <p className="flex items-baseline justify-between gap-3 px-2 pt-1">
        <span className="font-bold text-navy-900">{capital(monthName(month.month))}</span>
        <span className="font-black text-navy-900 tabular-nums">{formatPln(month.total)}</span>
      </p>
      {month.lines.length === 0 ? (
        <p className="px-2 pt-0.5 pb-1 text-navy-500">Bez wypłat w tym miesiącu.</p>
      ) : (
        <ul className="mt-1">
          {month.lines.map((line) => (
            <li key={`${line.parent}-${line.payer}`}>
              <button
                type="button"
                onClick={() => onSelect(line.payment_ids[0])}
                className="flex w-full items-center gap-2.5 rounded-xl px-2 py-1.5 text-left transition-colors hover:bg-white"
              >
                <span
                  className="h-7 w-1.5 shrink-0 rounded-full"
                  style={{
                    background: fromEmployer(line)
                      ? stripes(FILL[line.parent][light(line) ? 'option' : 'leave'])
                      : FILL[line.parent][light(line) ? 'option' : 'leave'],
                  }}
                />
                <span className="min-w-0 flex-1">
                  <span className="block font-bold text-navy-900">
                    {WHO[line.parent]} · {lower(periods(line))}
                  </span>
                  <span className="block text-xs text-navy-500">Wypłaca: {line.payer_label}</span>
                </span>
                <span className="shrink-0 font-bold text-navy-900 tabular-nums">{formatPln(line.amount)}</span>
                <ChevronRight className="size-4 shrink-0 text-navy-300" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="px-2 pt-1 pb-1 text-xs text-navy-400">Kwota za dni tego miesiąca, nie dzień przelewu.</p>
    </div>
  )
}

const stripes = (color: string) =>
  `repeating-linear-gradient(135deg, ${color} 0 3px, color-mix(in srgb, ${color} 45%, white) 3px 6px)`

/** "pracodawca", "zleceniodawca" or both, from the engine's own labels. */
function employerWord(lines: MonthlyLine[]): string {
  const contract = lines.some((l) => l.payer_label.startsWith('Zleceniodawca'))
  const employer = lines.some((l) => l.payer_label.startsWith('Pracodawca'))
  return contract && employer ? 'pracodawca albo zleceniodawca' : contract ? 'zleceniodawca' : 'pracodawca'
}

/** A month whose name is always shown: the first, January (with the year) and this month. */
function forced(columns: Column[], i: number, thisMonth: string): boolean {
  const column = columns[i]
  if (!column || column.kind === 'gap') return false
  return i === 0 || column.month.month.endsWith('-01') || column.month.month === thisMonth
}

/** What a screen reader hears for one month. */
function describe(month: MonthlyPayment): string {
  if (month.lines.length === 0) return `${monthName(month.month)}: bez wypłat`
  const lines = month.lines
    .map((line) => `${WHO[line.parent]} ${formatPln(line.amount)}, wypłaca ${line.payer_label}`)
    .join('; ')
  return `${monthName(month.month)}: razem ${formatPln(month.total)}. ${lines}`
}
