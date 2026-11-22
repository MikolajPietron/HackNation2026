// "Pieniądze" (FUNKCJE F4, F12; the brief's question "ile pieniędzy dostanie mama i tata"):
// what comes in each calendar month and who pays it (MonthChart, from Timeline.monthly), the
// total, the periods with their amounts, and the choice between 100% + 70% and 81,5%. Every
// number is the engine's.
import { useEffect, useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { calculateTimeline } from '@/api'
import { MonthChart } from '@/components/money/MonthChart'
import { Emphasis } from '@/components/ui/emphasis'
import type { PlanApply } from '@/hooks/usePlanChange'
import { Illustration } from '@/components/ui/illustration'
import { formatShortDate } from '@/lib/dates'
import { ICONS, segmentIcon } from '@/lib/icons'
import { formatPln, formatRate, moneyNote } from '@/lib/money'
import { periodName } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { Payment, Scenario, Timeline } from '@/types'

const WHO = { mother: 'Mama', father: 'Tata' } as const

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
  onApply,
}: {
  timeline: Timeline
  scenario: Scenario | null
  hoveredId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
  onWhy: () => void
  /** Change the plan from the interface (with undo). */
  onApply: PlanApply
}) {
  const payments = useMemo(
    () =>
      [...timeline.payments].sort(
        (a, b) => (a.lane === b.lane ? 0 : a.lane === 'mother' ? -1 : 1) || a.start.localeCompare(b.start),
      ),
    [timeline.payments],
  )
  const payer = moneyNote(timeline, 'payer')
  const [periodsOpen, setPeriodsOpen] = useState(false)
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
          <Total timeline={timeline} />
        </div>
        <button
          type="button"
          onClick={onWhy}
          className="flex h-9 shrink-0 items-center gap-0.5 rounded-full px-3 text-sm font-bold text-zus-700 transition-colors hover:bg-zus-50"
        >
          Dlaczego tyle? <ChevronRight className="size-4" />
        </button>
      </header>

      <MonthChart timeline={timeline} hoveredId={hoveredId} onSelect={onSelect} />

      {/* On a phone the periods repeat what the chart shows: they open on demand. */}
      <button
        type="button"
        onClick={() => setPeriodsOpen((o) => !o)}
        aria-expanded={periodsOpen}
        className="mt-4 flex w-full items-center justify-between rounded-2xl border border-line px-4 py-3 text-sm font-bold text-navy-900 lg:hidden"
      >
        Okresy i kwoty ({payments.length})
        <ChevronDown className={cn('size-4 text-navy-500 transition-transform duration-200', periodsOpen && 'rotate-180')} />
      </button>
      <ul className={cn('mt-4 divide-y divide-line', !periodsOpen && 'hidden lg:block')}>
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

      <RateChoice timeline={timeline} scenario={scenario} onApply={onApply} onSelect={onSelect} />
    </section>
  )
}

/** All the money of the plan, as the engine added it up (Timeline.money_total). */
function Total({ timeline }: { timeline: Timeline }) {
  const total = timeline.money_total
  if (!total) return null
  const both = total.mother > 0 && total.father > 0
  return (
    <p className="text-sm text-navy-500">
      Razem <b className="text-navy-900 tabular-nums">{formatPln(total.total)}</b>
      {both && (
        <span className="tabular-nums">
          {' '}
          · mama {formatPln(total.mother)} · tata {formatPln(total.father)}
        </span>
      )}
    </p>
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
  onApply,
  onSelect,
}: {
  timeline: Timeline
  scenario: Scenario | null
  onApply: PlanApply
  onSelect: (id: string) => void
}) {
  const note = moneyNote(timeline, 'rate-815')
  // How the choice is made for real (the engine's words: the written request, by when, where).
  const how = timeline.notes.find((n) => n.id === 'rate-815-how')
  const request = timeline.documents.find((d) => d.id === 'rate-815-request')
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
      hint: 'bez dodatkowego wniosku',
      selected: !chosen815,
      rows: [
        ['Macierzyński', monthly(standard, 'maternity')],
        ['Rodzicielski', monthly(standard, 'parental')],
      ] as const,
      value: false,
      done: 'Zostajecie przy 100% i 70%',
    },
    {
      id: 'flat',
      title: '81,5% za urlop macierzyński i rodzicielski',
      hint: 'na wniosek',
      selected: chosen815,
      rows: [
        ['Macierzyński', monthly(flat, 'maternity')],
        ['Rodzicielski', monthly(flat, 'parental')],
      ] as const,
      value: true,
      done: 'Wybrano 81,5% za urlop macierzyński i rodzicielski',
    },
  ]

  return (
    <section id="rate-choice" className="mt-5 scroll-mt-6 border-t border-line pt-5">
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
                onClick={() =>
                  void onApply(
                    { rate_815: option.value },
                    option.done,
                    option.value && deadline
                      ? `Wniosek o 81,5% złóż najpóźniej ${formatShortDate(deadline.date)}.`
                      : undefined,
                  )
                }
                className="mt-3 flex h-9 items-center gap-0.5 rounded-full px-3 text-sm font-bold text-zus-700 transition-colors hover:bg-zus-50"
              >
                Wybieram to <ChevronRight className="size-4" />
              </button>
            )}
          </motion.div>
        ))}
      </div>
      {how && (
        <div className="mt-3 flex gap-3 rounded-2xl bg-navy-50/60 px-4 py-3">
          <Illustration src={ICONS.koperta} size="hint" className="mt-0.5" />
          <div className="min-w-0 text-sm leading-relaxed text-navy-700">
            <p className="font-bold text-navy-900">{how.title}</p>
            <p className="mt-0.5">
              <Emphasis text={how.text} className="text-navy-900" />
            </p>
            <p className="mt-1 text-xs text-navy-500">
              „Wybieram to” zmienia tylko Wasz plan w aplikacji. Zasiłek zmienia dopiero ten wniosek.
            </p>
            {request && (
              <button
                type="button"
                onClick={() => onSelect(request.id)}
                className="mt-1.5 flex items-center gap-0.5 font-bold text-zus-700 hover:text-zus-900"
              >
                Wniosek na osi <ChevronRight className="size-4" />
              </button>
            )}
          </div>
        </div>
      )}
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
