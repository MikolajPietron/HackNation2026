// "Pieniądze" (FUNKCJE F4, F12; the brief's question "ile pieniędzy dostanie mama i tata"):
// a step chart of what comes in each month and who it is for, the periods with their amounts,
// who pays, and the choice between 100% + 70% and 81,5%. Every number is the engine's; the chart
// only draws the monthly amounts of the periods side by side (FUNKCJE: dips are visible).
import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { ChevronRight } from 'lucide-react'
import { calculateTimeline } from '@/api'
import { Emphasis } from '@/components/ui/emphasis'
import { Illustration } from '@/components/ui/illustration'
import { dayNumber, formatDayMonthShort, formatShortDate, monthCells } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { ICONS, segmentIcon } from '@/lib/icons'
import { formatPln, formatPlnShort, formatRate, moneyNote } from '@/lib/money'
import { periodName } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { Payment, Scenario, Timeline } from '@/types'

const WHO = { mother: 'Mama', father: 'Tata' } as const
const CHART_HEIGHT = 168
const LABEL_SPACE = 22

/** Solid when the period is set, light when it is still to decide; green mother, navy father. */
const FILL = {
  mother: { leave: 'var(--color-zus-600)', option: 'var(--color-zus-300)' },
  father: { leave: 'var(--color-navy-700)', option: 'var(--color-navy-300)' },
} as const

export function MoneyCard({
  timeline,
  scenario,
  hoveredId,
  onHover,
  onSelect,
  onWhy,
  onAsk,
}: {
  timeline: Timeline
  scenario: Scenario | null
  hoveredId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
  onWhy: () => void
  onAsk: (prompt: string) => void
}) {
  const payments = useMemo(
    () =>
      [...timeline.payments].sort(
        (a, b) => (a.lane === b.lane ? 0 : a.lane === 'mother' ? -1 : 1) || a.start.localeCompare(b.start),
      ),
    [timeline.payments],
  )
  const payer = moneyNote(timeline, 'payer')
  const tone = (p: Payment) =>
    timeline.segments.find((s) => s.id === p.segment_id)?.tone === 'option' ? 'option' : 'leave'

  if (payments.length === 0) return null
  return (
    <section aria-labelledby="money-title" className="rounded-4xl border border-line px-4 pt-5 pb-5 sm:px-5">
      <header className="flex items-start gap-3">
        <Illustration src={ICONS.pieniadze} size="event" className="bg-navy-50/60" />
        <div className="min-w-0 flex-1">
          <h2 id="money-title" className="text-lg font-bold text-navy-900">
            Pieniądze
          </h2>
          <p className="hidden text-sm text-navy-500 sm:block">Ile wpływa miesięcznie, za co i kto płaci</p>
        </div>
        <button
          type="button"
          onClick={onWhy}
          className="flex h-9 shrink-0 items-center gap-0.5 rounded-full px-3 text-sm font-bold text-zus-700 transition-colors hover:bg-zus-50"
        >
          Dlaczego tyle? <ChevronRight className="size-4" />
        </button>
      </header>

      <StepChart
        timeline={timeline}
        payments={payments}
        tone={tone}
        hoveredId={hoveredId}
        onHover={onHover}
        onSelect={onSelect}
      />

      <ul className="mt-4 divide-y divide-line">
        {payments.map((payment) => {
          const segment = timeline.segments.find((s) => s.id === payment.segment_id)
          const option = tone(payment) === 'option'
          return (
            <li key={payment.id}>
              <button
                type="button"
                onClick={() => onSelect(payment.id)}
                onMouseEnter={() => onHover(payment.id)}
                onMouseLeave={() => onHover(null)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-2xl px-2 py-2.5 text-left transition-colors duration-150',
                  hoveredId === payment.id ? 'bg-navy-50' : 'hover:bg-navy-50/60',
                )}
              >
                <span
                  className="h-9 w-1.5 shrink-0 rounded-full"
                  style={{ background: FILL[payment.lane][option ? 'option' : 'leave'] }}
                />
                {segment && <Illustration src={segmentIcon(segment)} size="hint" />}
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <span className="font-bold text-navy-900">
                      {WHO[payment.lane]} · {segment ? periodName(segment) : payment.title}
                    </span>
                    {option && (
                      <span className="rounded-full bg-zus-50 px-2 py-0.5 text-[11px] font-bold text-zus-700">
                        do wyboru
                      </span>
                    )}
                  </span>
                  <span className="block text-sm text-navy-500 tabular-nums">
                    {formatShortDate(payment.start)} – {formatShortDate(payment.end)} · {formatRate(payment.rate)}
                  </span>
                </span>
                <span className="shrink-0 text-right tabular-nums">
                  <span className="block font-bold text-navy-900">
                    {formatPln(payment.monthly)}
                    <span className="text-sm font-normal text-navy-500"> / mies.</span>
                  </span>
                  <span className="block text-sm text-navy-500">
                    razem {formatPln(payment.total)}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>

      {payer && (
        <p className="mt-3 flex gap-2.5 rounded-2xl bg-navy-50/60 px-4 py-3 text-sm leading-relaxed text-navy-700">
          <Illustration src={ICONS.koperta} size="hint" />
          <span>
            <b className="text-navy-900">Kto płaci: </b>
            <Emphasis text={payer.text} className="text-navy-900" />
          </span>
        </p>
      )}

      <RateChoice timeline={timeline} scenario={scenario} onAsk={onAsk} />
    </section>
  )
}

/**
 * The monthly amount over time, a step per period: the mother's at the bottom, the father's on
 * top where they overlap. A drop to a lower rate is marked, so the "dips" are easy to see.
 */
function StepChart({
  timeline,
  payments,
  tone,
  hoveredId,
  onHover,
  onSelect,
}: {
  timeline: Timeline
  payments: Payment[]
  tone: (p: Payment) => 'leave' | 'option'
  hoveredId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const reduce = useReducedMotion()
  useEffect(() => {
    const element = box.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const from = Math.min(...payments.map((p) => dayNumber(p.start)))
  const to = Math.max(...payments.map((p) => dayNumber(p.end) + 1))
  const x = (day: number) => ((day - from) / Math.max(1, to - from)) * width

  const motherOn = (day: number) =>
    payments.find((p) => p.lane === 'mother' && dayNumber(p.start) <= day && day <= dayNumber(p.end))
  // Where a father's bar starts: on top of the mother's bar of his first day.
  const under = (p: Payment) => (p.lane === 'father' ? (motherOn(dayNumber(p.start))?.monthly ?? 0) : 0)
  // The scale only: the tallest stack. No amount is shown from it.
  const top = Math.max(1, ...payments.map((p) => p.monthly + under(p)))
  const height = (amount: number) => (amount / top) * (CHART_HEIGHT - LABEL_SPACE)
  const months = monthCells(from, to)
  const today = dayNumber(timeline.today)
  const hovered = payments.find((p) => p.id === hoveredId) ?? null

  // A period that pays less than the one before it, for the same parent and right after it.
  const dips = payments.filter((p) => {
    const before = payments.find((q) => q.lane === p.lane && dayNumber(q.end) + 1 === dayNumber(p.start))
    return before && p.monthly < before.monthly
  })

  return (
    <div className="relative mt-4" ref={box}>
      {width > 0 && (
        <svg width={width} height={CHART_HEIGHT + 24} role="img" aria-label="Zasiłek miesięcznie w czasie">
          {/* Month lines. */}
          {months.map((month) =>
            month.start > from ? (
              <line
                key={month.start}
                x1={x(month.start)}
                x2={x(month.start)}
                y1={0}
                y2={CHART_HEIGHT}
                stroke="var(--color-line)"
                strokeWidth={1}
              />
            ) : null,
          )}
          <line x1={0} x2={width} y1={CHART_HEIGHT} y2={CHART_HEIGHT} stroke="var(--color-navy-200)" />
          {payments.map((p) => {
            const left = x(dayNumber(p.start))
            const span = Math.max(1, x(dayNumber(p.end) + 1) - left - 1)
            const base = under(p) ? height(under(p)) + 2 : 0
            const h = height(p.monthly)
            const y = CHART_HEIGHT - base - h
            const light = tone(p) === 'option'
            const inside = p.lane === 'mother' && h >= 22
            const dip = dips.includes(p)
            return (
              <g
                key={p.id}
                className="cursor-pointer"
                onMouseEnter={() => onHover(p.id)}
                onMouseLeave={() => onHover(null)}
                onClick={() => onSelect(p.id)}
              >
                <motion.rect
                  x={left}
                  width={span}
                  rx={4}
                  initial={false}
                  animate={{ y, height: h, opacity: hovered && hovered.id !== p.id ? 0.35 : 1 }}
                  transition={reduce ? { duration: 0 } : { duration: 0.45, ease: EASE_OUT }}
                  fill={FILL[p.lane][tone(p)]}
                />
                {span >= 64 && (
                  <text
                    x={left + 8}
                    y={inside ? y + 16 : y - 6}
                    className={cn(
                      'text-[11px] font-bold tabular-nums',
                      inside ? (light ? 'fill-zus-900' : 'fill-white') : 'fill-navy-700',
                    )}
                  >
                    {formatPlnShort(p.monthly)}
                  </text>
                )}
                {dip && span >= 90 && h >= 40 && (
                  <text
                    x={left + 8}
                    y={CHART_HEIGHT - base - 8}
                    className={cn('text-[10px] font-black', light ? 'fill-zus-900' : 'fill-white')}
                  >
                    ↓ {formatRate(p.rate)}
                  </text>
                )}
              </g>
            )
          })}
          {today > from && today < to && (
            <g>
              <line x1={x(today)} x2={x(today)} y1={0} y2={CHART_HEIGHT} stroke="var(--color-navy-900)" strokeWidth={1.5} strokeDasharray="3 3" />
              <text x={x(today) + 4} y={10} className="fill-navy-900 text-[10px] font-bold">
                dziś
              </text>
            </g>
          )}
          {months.map((month, index) => {
            const left = Math.max(0, x(month.start))
            const next = months[index + 1]
            if ((next && x(next.start) - left < 36) || left + 28 > width) return null
            return (
              <text key={`m-${month.start}`} x={left + 3} y={CHART_HEIGHT + 16} className="fill-navy-400 text-[10px] font-bold">
                {month.label.replace('.', '')}
                {month.label.startsWith('sty') || index === 0 ? ` ${String(month.year).slice(2)}` : ''}
              </text>
            )
          })}
        </svg>
      )}
      <AnimatePresence>
        {hovered && width > 0 && (
          <motion.div
            key={hovered.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
            transition={{ duration: 0.15, ease: EASE_OUT }}
            className="pointer-events-none absolute top-0 z-10 w-56 rounded-2xl bg-navy-900 px-3 py-2 text-xs text-white shadow-[0_12px_30px_-12px_rgb(26_36_56/0.6)]"
            style={{
              left: Math.min(Math.max(0, x(dayNumber(hovered.start))), Math.max(0, width - 224)),
            }}
          >
            <p className="font-bold">
              {WHO[hovered.lane]} · {formatRate(hovered.rate)}
            </p>
            <p className="mt-0.5 text-sm font-bold tabular-nums">{formatPln(hovered.monthly)} / mies.</p>
            <p className="mt-0.5 text-white/70">
              {formatDayMonthShort(hovered.start)} – {formatShortDate(hovered.end)}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
      <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs font-bold text-navy-500">
        {(['mother', 'father'] as const)
          .filter((lane) => payments.some((p) => p.lane === lane))
          .map((lane) => (
            <li key={lane} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm" style={{ background: FILL[lane].leave }} />
              {WHO[lane]}
            </li>
          ))}
        {payments.some((p) => tone(p) === 'option') && (
          <li className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: FILL.mother.option }} />
            jaśniej: do wyboru
          </li>
        )}
      </ul>
    </div>
  )
}

/**
 * 100% + 70% or 81,5% for the whole leave (ustawa art. 31): the same plan counted both ways by
 * the engine, the monthly amounts side by side, the engine's comparison in words, and the day the
 * written request is due.
 */
function RateChoice({
  timeline,
  scenario,
  onAsk,
}: {
  timeline: Timeline
  scenario: Scenario | null
  onAsk: (prompt: string) => void
}) {
  const note = moneyNote(timeline, 'rate-815')
  const deadline = timeline.markers.find((m) => m.id === 'rate-815-deadline')
  const chosen815 = scenario?.rate_815 === true
  const [other, setOther] = useState<Timeline | null>(null)
  const hasMother = timeline.payments.some((p) => p.lane === 'mother')

  useEffect(() => {
    if (!scenario || !note || !hasMother) return
    const controller = new AbortController()
    calculateTimeline({ ...scenario, rate_815: !chosen815 }, controller.signal)
      .then(setOther)
      .catch(() => setOther(null))
    return () => controller.abort()
  }, [scenario, note, hasMother, chosen815])

  if (!note || !hasMother || !scenario) return null
  const standard = chosen815 ? other : timeline
  const flat = chosen815 ? timeline : other
  const passed = deadline ? deadline.date < timeline.today : false
  const monthly = (t: Timeline | null, kind: 'maternity' | 'parental') =>
    t?.payments.find((p) => p.lane === 'mother' && p.segment_id.startsWith(kind))?.monthly

  const options = [
    {
      id: 'standard',
      title: '100% i 70%',
      hint: 'bez wniosku',
      selected: !chosen815,
      rows: [
        ['Macierzyński', monthly(standard, 'maternity')],
        ['Rodzicielski', monthly(standard, 'parental')],
      ] as const,
      prompt: 'Zostaję przy 100% za urlop macierzyński i 70% za rodzicielski',
    },
    {
      id: 'flat',
      title: '81,5% przez cały czas',
      hint: 'na wniosek',
      selected: chosen815,
      rows: [
        ['Macierzyński', monthly(flat, 'maternity')],
        ['Rodzicielski', monthly(flat, 'parental')],
      ] as const,
      prompt: 'Chcę dostawać 81,5% przez cały urlop macierzyński i rodzicielski',
    },
  ]

  return (
    <section className="mt-5 border-t border-line pt-5">
      <h3 className="flex flex-wrap items-center gap-x-3 gap-y-1 font-bold text-navy-900">
        Jak wolisz dostawać zasiłek?
        {deadline && (
          <span
            className={cn(
              'rounded-full px-2.5 py-0.5 text-xs font-bold',
              passed ? 'bg-alert-50 text-alert-600' : 'bg-sun-100 text-sun-700',
            )}
          >
            {passed ? `termin minął ${formatShortDate(deadline.date)}` : `wniosek do ${formatShortDate(deadline.date)}`}
          </span>
        )}
      </h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {options.map((option) => (
          <motion.div
            key={option.id}
            layout
            className={cn(
              'rounded-3xl border p-4 transition-[border-color,background-color] duration-200',
              option.selected ? 'border-zus-600 bg-zus-50/60 shadow-[0_0_0_1px_var(--color-zus-600)]' : 'border-line',
            )}
          >
            <p className="flex items-center justify-between gap-2">
              <span className="font-bold text-navy-900">{option.title}</span>
              <span className="text-xs font-bold text-navy-400">
                {option.selected ? (scenario.rate_815 === null ? 'domyślnie' : 'Wasz wybór') : option.hint}
              </span>
            </p>
            <dl className="mt-2 space-y-1 text-sm">
              {option.rows.map(([label, amount]) => (
                <div key={label} className="flex items-baseline justify-between gap-3">
                  <dt className="text-navy-500">{label}</dt>
                  <dd className="font-bold text-navy-900 tabular-nums">
                    {amount === undefined ? (
                      <span className="inline-block h-4 w-24 animate-pulse rounded bg-navy-100 align-middle" />
                    ) : (
                      <>
                        {formatPln(amount)}
                        <span className="font-normal text-navy-500"> / mies.</span>
                      </>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
            {!option.selected && !passed && (
              <button
                type="button"
                onClick={() => onAsk(option.prompt)}
                className="mt-3 flex h-9 items-center gap-0.5 rounded-full px-3 text-sm font-bold text-zus-700 transition-colors hover:bg-zus-50"
              >
                Wybieram to <ChevronRight className="size-4" />
              </button>
            )}
          </motion.div>
        ))}
      </div>
      <Folded text={note.text} />
    </section>
  )
}

/** A long text of the engine, two lines until opened. */
function Folded({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-3 text-sm leading-relaxed text-navy-500">
      <p className={cn(!open && 'line-clamp-2')}>
        <Emphasis text={text} className="text-navy-900" />
      </p>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="mt-1 font-bold text-zus-700 underline-offset-4 hover:underline"
      >
        {open ? 'Mniej' : 'Więcej'}
      </button>
    </div>
  )
}
