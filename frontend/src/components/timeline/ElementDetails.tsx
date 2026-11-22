import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, ChevronRight, FileText, Lock, Wallet } from 'lucide-react'
import { Emphasis } from '@/components/ui/emphasis'
import { formatDayMonthLong, formatDistance, formatShortDate } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { formatPln, formatRate, paymentFor } from '@/lib/money'
import { daysLeftLabel } from '@/lib/plan'
import { sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { SourceRef, Timeline } from '@/types'
import type { TimelineItem } from './items'

interface Props {
  item: TimelineItem
  timeline: Timeline
  onSelect: (id: string) => void
  /** Open the filled-in request for a document (a leave request). */
  onFill?: (documentId: string) => void
}

interface Fact {
  label: string
  value: string
}

/**
 * What the parent needs about one element. The facts come first and big (from, to, how long;
 * or when and how far away), the explanation with its numbers in bold, the sources last.
 */
export function ElementDetails({ item, timeline, onSelect, onFill }: Props) {
  return (
    <div className="text-[15px] leading-relaxed text-navy-700">
      <Body item={item} timeline={timeline} onSelect={onSelect} onFill={onFill} />
      <Sources sources={item.element.sources} text={elementText(item)} />
    </div>
  )
}

const weeksOrDays = (days: number) => (days % 7 === 0 ? `${days / 7} tyg.` : `${days} dni`)

function Body({ item, timeline, onSelect, onFill }: Props) {
  switch (item.kind) {
    case 'segment': {
      const s = item.element
      const documents = timeline.documents.filter((d) => d.segment_id === s.id)
      const payment = paymentFor(timeline, s.id)
      return (
        <>
          <Title>{s.title}</Title>
          <Facts
            facts={[
              { label: 'Od', value: formatShortDate(s.start) },
              { label: 'Do', value: formatShortDate(s.end) },
              { label: 'Ile', value: weeksOrDays(s.days) },
            ]}
          />
          <p className="mt-5">
            <Emphasis text={s.summary} />
          </p>
          <Bullets items={s.details} />
          {payment && (
            <button
              type="button"
              onClick={() => onSelect(payment.id)}
              className="group mt-5 flex w-full items-center gap-3 rounded-2xl border border-sun-300 bg-sun-100/50 px-4 py-3 text-left transition-[border-color,transform] duration-150 hover:border-sun-400 active:scale-[0.98]"
            >
              <Wallet className="size-4 shrink-0 text-sun-700" />
              <span className="min-w-0 flex-1">
                <span className="block font-bold text-navy-900">
                  Zasiłek: {formatPln(payment.monthly)} miesięcznie
                </span>
                <span className="block text-sm text-navy-500">
                  {formatRate(payment.rate)} podstawy · za cały okres {formatPln(payment.total)}
                </span>
              </span>
              <ChevronRight className="size-4 shrink-0 text-navy-400 transition-transform group-hover:translate-x-0.5" />
            </button>
          )}
          {documents.length > 0 && (
            <ul className="mt-5 space-y-2">
              {documents.map((d) => (
                <li key={d.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(d.id)}
                    className="group flex w-full items-center gap-3 rounded-2xl border border-line px-4 py-3 text-left transition-[border-color,transform] duration-150 hover:border-navy-200 active:scale-[0.98]"
                  >
                    <FileText className="size-4 shrink-0 text-sun-700" />
                    <span className="min-w-0 flex-1 font-bold text-navy-900">{d.title}</span>
                    <span className="shrink-0 text-sm font-bold text-navy-500">
                      {d.done ? 'już jest' : `na ${formatDayMonthLong(d.needed_by)}`}
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-navy-400 transition-transform group-hover:translate-x-0.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )
    }
    case 'marker': {
      const m = item.element
      return (
        <>
          <Title>{m.title}</Title>
          <Facts
            facts={[
              { label: 'Kiedy', value: formatShortDate(m.date) },
              {
                label: 'Od dziś',
                value:
                  m.irreversible && m.irreversible.days_left >= 0
                    ? daysLeftLabel(m.irreversible.days_left)
                    : formatDistance(timeline.today, m.date),
              },
            ]}
          />
          {m.irreversible && m.irreversible.days_left >= 0 && (
            <p className="mt-5 flex gap-3 rounded-2xl border border-sun-300 bg-sun-100/50 px-4 py-3">
              <Lock className="mt-1 size-4 shrink-0 text-sun-700" strokeWidth={2.5} />
              <span>
                <span className="block font-bold text-navy-900">Punkt bez powrotu</span>
                {m.irreversible.lost}
              </span>
            </p>
          )}
          <p className="mt-5">
            <Emphasis text={m.summary} />
          </p>
          <Bullets items={m.details} />
        </>
      )
    }
    case 'payment': {
      const p = item.element
      const segment = timeline.segments.find((s) => s.id === p.segment_id)
      return (
        <>
          <Title>{p.title}</Title>
          <Facts
            facts={[
              { label: 'Miesięcznie', value: formatPln(p.monthly) },
              { label: 'Stawka', value: formatRate(p.rate) },
              { label: `Za ${p.days} dni`, value: formatPln(p.total) },
            ]}
          />
          <p className="mt-5">
            <Emphasis text={p.summary} />
          </p>
          <Bullets items={p.details} />
          {segment && (
            <button
              type="button"
              onClick={() => onSelect(segment.id)}
              className="group mt-4 flex items-center gap-1 text-sm font-bold text-zus-700"
            >
              Dotyczy: {segment.title}
              <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </button>
          )}
        </>
      )
    }
    case 'document': {
      const d = item.element
      const segment = timeline.segments.find((s) => s.id === d.segment_id)
      return (
        <>
          <Title>{d.title}</Title>
          <Facts
            facts={[
              // A Labour Code deadline is a deadline; otherwise the day is only when the leave
              // or the benefit starts (Document.deadline).
              d.deadline
                ? { label: 'Złóż najpóźniej', value: formatShortDate(d.deadline) }
                : { label: d.form ? 'Na dzień startu' : 'Potrzebne na', value: formatShortDate(d.needed_by) },
              { label: 'Od dziś', value: formatDistance(timeline.today, d.deadline ?? d.needed_by) },
              { label: 'Status', value: d.done ? 'już jest' : d.form ? 'do złożenia' : 'do zdobycia' },
            ]}
          />
          <p className="mt-5">
            <Emphasis text={d.rule} />
          </p>
          {onFill && d.form && !d.done && (
            <button
              type="button"
              onClick={() => onFill(d.id)}
              className="mt-4 flex h-11 items-center gap-2 rounded-full bg-zus-600 px-5 text-sm font-bold text-white transition-colors hover:bg-zus-700"
            >
              Wypełnij wniosek <ChevronRight className="size-4" />
            </button>
          )}
          {segment && (
            <button
              type="button"
              onClick={() => onSelect(segment.id)}
              className="group mt-4 flex items-center gap-1 text-sm font-bold text-zus-700"
            >
              Dotyczy: {segment.title}
              <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </button>
          )}
        </>
      )
    }
  }
}

function Title({ children }: { children: string }) {
  return (
    <h3 className="pr-10 text-2xl leading-tight font-bold tracking-tight text-navy-900">{children}</h3>
  )
}

/** The numbers that matter, large enough to read without reading the text. */
function Facts({ facts }: { facts: Fact[] }) {
  return (
    <dl
      className="mt-4 grid gap-2"
      style={{ gridTemplateColumns: `repeat(${facts.length}, minmax(0, 1fr))` }}
    >
      {facts.map(({ label, value }) => (
        <div key={label} className="rounded-2xl bg-navy-50/70 px-4 py-3">
          <dt className="text-xs font-bold text-navy-500">{label}</dt>
          <dd className="mt-0.5 text-lg leading-tight font-bold whitespace-nowrap text-navy-900">
            {value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function Bullets({ items }: { items: string[] }) {
  if (items.length === 0) return null
  return (
    <ul className="mt-3 space-y-1.5">
      {items.map((text) => (
        <li key={text} className="flex gap-3">
          <span className="mt-[0.6em] size-1.5 shrink-0 rounded-full bg-navy-200" />
          <span>
            <Emphasis text={text} />
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Literal quotes: the guide first, the Labour Code behind a toggle so the details stay short. */
/** The element's own sentence, to see which numbers in it its quotes must back. */
function elementText(item: TimelineItem): string {
  switch (item.kind) {
    case 'segment':
    case 'marker':
    case 'payment':
      return item.element.summary
    case 'document':
      return item.element.rule
  }
}

const numbersIn = (text: string) => new Set(text.match(/\d+(?:,\d+)?/g) ?? [])

/**
 * Literal quotes: the guide first, the law (Labour Code, ustawa zasiłkowa) behind a toggle so the
 * details stay short. The toggle starts open when a number the element states is only in the law
 * (e.g. 31 weeks for twins: the guide quotes only the 20 weeks of one child).
 */
function Sources({ sources, text }: { sources: SourceRef[]; text: string }) {
  // The ZUS Załącznik is shown with the guide: both are ZUS's own words, not the law.
  const guide = sources.filter((s) => s.doc === 'przewodnik' || s.doc === 'zalacznik')
  // The law: the Labour Code, the ustawa zasiłkowa and the two regulations the request forms
  // quote (leave requests, benefit documents).
  const law = sources.filter((s) => s.doc !== 'przewodnik' && s.doc !== 'zalacznik')
  const inGuide = numbersIn(guide.map((s) => s.quote).join(' '))
  const inLaw = numbersIn(law.map((s) => s.quote).join(' '))
  const onlyInLaw = [...numbersIn(text)].some((n) => inLaw.has(n) && !inGuide.has(n))
  const [lawOpen, setLawOpen] = useState(guide.length === 0 || onlyInLaw)
  if (sources.length === 0) return null
  return (
    <section className="mt-6 border-t border-line pt-5">
      <p className="text-sm font-bold text-navy-900">Źródło</p>
      <div className="mt-3 space-y-4">
        {guide.map((source) => (
          <Quote key={source.quote} source={source} />
        ))}
      </div>
      {law.length > 0 && (
        <div className={cn(guide.length > 0 && 'mt-4')}>
          <button
            type="button"
            onClick={() => setLawOpen((open) => !open)}
            aria-expanded={lawOpen}
            className="flex items-center gap-1.5 text-sm font-bold text-zus-700"
          >
            {lawToggle(law)}
            <ChevronDown
              className={cn('size-4 transition-transform duration-200', lawOpen && 'rotate-180')}
            />
          </button>
          <AnimatePresence initial={false}>
            {lawOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
                transition={{ duration: 0.22, ease: EASE_OUT }}
                className="overflow-hidden"
              >
                <div className="space-y-4 pt-3">
                  {law.map((source) => (
                    <Quote key={source.quote} source={source} />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </section>
  )
}

/** "Przepis z Kodeksu pracy", "Przepisy ustawy zasiłkowej (4)", "Przepisy (6)". */
const FROM: Record<string, string> = {
  kp: ' z Kodeksu pracy',
  ustawa: ' ustawy zasiłkowej',
  rozp_wnioski: ' rozporządzenia o wnioskach',
  rozp_zasilki: ' rozporządzenia o dokumentach',
}

function lawToggle(law: SourceRef[]): string {
  const docs = new Set(law.map((s) => s.doc))
  const from = docs.size > 1 ? '' : (FROM[[...docs][0]] ?? '')
  return law.length === 1 ? `Przepis${from}` : `Przepisy${from} (${law.length})`
}

function Quote({ source }: { source: SourceRef }) {
  return (
    <figure>
      <blockquote className="text-navy-700">„{source.quote}”</blockquote>
      <figcaption className="mt-1 text-sm text-navy-400">{sourceLabel(source)}</figcaption>
    </figure>
  )
}
