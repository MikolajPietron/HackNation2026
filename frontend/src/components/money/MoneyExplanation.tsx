// "Dlaczego tyle?" (FUNKCJE F5): every amount with its base, the steps that make it and the rule
// behind each step, then the way from the base to the benefit of each period. All numbers are the
// engine's (Timeline.bases, Timeline.payments); this only lays them out.
import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Emphasis } from '@/components/ui/emphasis'
import { Illustration } from '@/components/ui/illustration'
import { formatShortDate } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { ICONS, segmentIcon } from '@/lib/icons'
import { formatPln, formatRate, moneyNote } from '@/lib/money'
import { periodName } from '@/lib/plan'
import { sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { BaseMonthStatus, BenefitBase, SourceRef, Timeline } from '@/types'

const WHO = { mother: 'Mama', father: 'Tata' } as const
const WHO_ICON = { mother: ICONS.mamaZDzieckiem, father: ICONS.tataZDzieckiem } as const

const STATUS: Record<BaseMonthStatus, { label: string; className: string }> = {
  full: { label: 'liczy się', className: 'bg-zus-50 text-zus-700' },
  'topped-up': { label: 'uzupełniony', className: 'bg-sun-100 text-sun-700' },
  skipped: { label: 'pominięty', className: 'bg-navy-50 text-navy-500' },
  outside: { label: 'poza okresem', className: 'bg-navy-50 text-navy-400' },
  'before-insurance': { label: 'przed ubezpieczeniem', className: 'bg-navy-50 text-navy-400' },
}

const monthName = new Intl.DateTimeFormat('pl-PL', { month: 'long', year: 'numeric', timeZone: 'UTC' })
const monthLabel = (month: string) => monthName.format(new Date(`${month}-01T00:00:00Z`))

export function MoneyExplanation({ timeline, onSelect }: { timeline: Timeline; onSelect: (id: string) => void }) {
  const payments = [...timeline.payments].sort(
    (a, b) => (a.lane === b.lane ? 0 : a.lane === 'mother' ? -1 : 1) || a.start.localeCompare(b.start),
  )
  const payer = moneyNote(timeline, 'payer')
  return (
    <div className="text-navy-700">
      <header className="pr-10">
        <h2 className="text-2xl font-bold tracking-tight text-navy-900">Dlaczego tyle?</h2>
        <p className="mt-2">
          Kwoty liczy kalkulator reguł, bez AI. Przy każdym kroku jest przepis, z którego wynika.
        </p>
      </header>

      {timeline.bases.map((base) => (
        <BaseSection key={base.parent} base={base} />
      ))}

      {payments.length > 0 && (
        <section className="mt-8">
          <h3 className="flex items-center gap-2 text-lg font-bold text-navy-900">
            <Illustration src={ICONS.pieniadze} size="hint" />
            Od podstawy do zasiłku
          </h3>
          <ul className="mt-2 divide-y divide-line">
            {payments.map((payment) => {
              const segment = timeline.segments.find((s) => s.id === payment.segment_id)
              return (
                <li key={payment.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(payment.id)}
                    className="flex w-full items-start gap-3 rounded-2xl px-2 py-3 text-left transition-colors hover:bg-navy-50/60"
                  >
                    {segment && <Illustration src={segmentIcon(segment)} size="hint" />}
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-baseline gap-x-2">
                        <span className="font-bold text-navy-900">
                          {WHO[payment.lane]} · {segment ? periodName(segment) : payment.title}
                        </span>
                        <span className="text-sm text-navy-500">
                          {formatShortDate(payment.start)} – {formatShortDate(payment.end)}
                        </span>
                      </span>
                      <span className="mt-1 block text-sm leading-relaxed tabular-nums">
                        {formatPln(payment.base)} × {formatRate(payment.rate)} ={' '}
                        <b className="text-navy-900">{formatPln(payment.monthly)} miesięcznie</b>
                        <span className="text-navy-400"> · </span>
                        {formatPln(payment.daily)} dziennie × {payment.days} dni ={' '}
                        <b className="text-navy-900">{formatPln(payment.total)}</b>
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
          <p className="mt-2 text-sm text-navy-500">
            Dzienna kwota to jedna trzydziesta miesięcznej; zasiłek przysługuje za każdy dzień, także
            wolny od pracy.
          </p>
        </section>
      )}

      {payer && (
        <section className="mt-8 rounded-3xl bg-navy-50/60 px-5 py-4">
          <h3 className="flex items-center gap-2 font-bold text-navy-900">
            <Illustration src={ICONS.koperta} size="hint" />
            {payer.title}
          </h3>
          <p className="mt-1.5 text-sm leading-relaxed">
            <Emphasis text={payer.text} className="text-navy-900" />
          </p>
          <Sources sources={payer.sources} />
        </section>
      )}
    </div>
  )
}

function BaseSection({ base }: { base: BenefitBase }) {
  return (
    <section className="mt-8">
      <div className="flex items-center gap-3">
        <Illustration src={WHO_ICON[base.parent]} size="event" className="bg-navy-50/60" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-navy-500">Podstawa wymiaru · {WHO[base.parent]}</p>
          <p className="text-2xl font-bold text-navy-900 tabular-nums">
            {formatPln(base.base)} <span className="text-base font-normal text-navy-500">miesięcznie</span>
          </p>
        </div>
      </div>
      <ol className="mt-4 space-y-3">
        {base.steps.map((step, index) => (
          <li key={step.text} className="flex gap-3">
            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-zus-50 text-xs font-black text-zus-700">
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="leading-relaxed">
                <Emphasis text={step.text} className="text-navy-900" />
              </p>
              <Sources sources={step.sources} />
            </div>
          </li>
        ))}
      </ol>
      {base.months.length > 0 && (
        <div className="mt-4 overflow-hidden rounded-2xl border border-line">
          <p className="bg-navy-50/60 px-4 py-2 text-xs font-bold text-navy-500">
            Miesiące z zaświadczenia płatnika
          </p>
          <ul className="divide-y divide-line text-sm">
            {base.months.map((month) => (
              <li key={month.month} className="flex items-center gap-3 px-4 py-2">
                <span className="min-w-0 flex-1 first-letter:uppercase">{monthLabel(month.month)}</span>
                <span className="text-navy-500 tabular-nums">{formatPln(month.amount)}</span>
                <span className="w-28 text-right font-bold text-navy-900 tabular-nums">
                  {month.counted === null ? '—' : formatPln(month.counted)}
                </span>
                <span className={cn('w-32 rounded-full px-2 py-0.5 text-center text-[11px] font-bold', STATUS[month.status].className)}>
                  {STATUS[month.status].label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

/** Source pills; one tap shows the quote under them. */
function Sources({ sources }: { sources: SourceRef[] }) {
  const [open, setOpen] = useState<number | null>(null)
  if (sources.length === 0) return null
  return (
    <div className="mt-1.5">
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source, index) => (
          <button
            key={`${source.quote}-${index}`}
            type="button"
            onClick={() => setOpen(open === index ? null : index)}
            aria-expanded={open === index}
            className={cn(
              'rounded-full px-2.5 py-0.5 text-xs font-bold transition-colors duration-150',
              open === index ? 'bg-navy-900 text-white' : 'bg-navy-50 text-navy-500 hover:text-navy-900',
            )}
          >
            {sourceLabel(source)}
          </button>
        ))}
      </div>
      <AnimatePresence initial={false}>
        {open !== null && sources[open] && (
          <motion.blockquote
            key={open}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0, transition: { duration: 0.12 } }}
            transition={{ duration: 0.22, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <p className="pt-2 text-sm leading-relaxed text-navy-700">„{sources[open].quote}”</p>
          </motion.blockquote>
        )}
      </AnimatePresence>
    </div>
  )
}
