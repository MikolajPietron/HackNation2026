// The result of a case: what AI read (marked), the two answers the jury checks (is the person
// insured on the day the right arises, and does the calculator agree with the decision of ZUS),
// the amounts and periods the engine computed, and the facts to correct by hand. Each answer is
// a picture, a word and one sentence; the detail is a click away.
import { useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, ChevronDown } from 'lucide-react'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import { Emphasis } from '@/components/ui/emphasis'
import { Illustration } from '@/components/ui/illustration'
import { formatShortDate } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { ICONS, segmentIcon } from '@/lib/icons'
import { formatPln, formatRate } from '@/lib/money'
import { length, periodName } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { CaseFacts, CaseResult } from '@/types'
import { CaseFactsForm } from './CaseFactsForm'

type Tone = 'good' | 'bad' | 'unknown'

const TONE: Record<Tone, string> = {
  good: 'text-zus-700',
  bad: 'text-alert-600',
  unknown: 'text-sun-700',
}

const pagesLabel = (pages: number[] | undefined) =>
  pages && pages.length > 0 ? `s. ${[...new Set(pages)].sort((a, b) => a - b).join(', ')}` : null

export function CaseResultView({
  result,
  category,
  busy,
  error,
  onBack,
  onRecalculate,
  onShowPlan,
}: {
  result: CaseResult
  category: string | null
  busy: boolean
  error: string | null
  onBack: () => void
  onRecalculate: (facts: CaseFacts) => void
  onShowPlan: () => void
}) {
  const [editing, setEditing] = useState(false)
  const factsRef = useRef<HTMLElement>(null)
  // No date of birth (or of taking the child in) in the documents: there is no timeline to show
  // yet, so the main button leads to the one field that is missing instead of being dead.
  const openFacts = () => {
    setEditing(true)
    requestAnimationFrame(() => factsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }
  const { facts, insurance, comparison, timeline } = result
  const covered: Tone = insurance.covered ? 'good' : insurance.covered === false ? 'bad' : 'unknown'
  const verdict: { tone: Tone; word: string } =
    comparison.match === true
      ? { tone: 'good', word: 'Zgodne z ZUS' }
      : comparison.match === false
        ? { tone: 'bad', word: 'Inaczej niż ZUS' }
        : comparison.zus === 'unknown'
          ? { tone: 'unknown', word: 'Brak decyzji w aktach' }
          : { tone: 'unknown', word: 'Do sprawdzenia' }
  const periods = (timeline?.segments ?? []).filter((s) => s.lane === 'mother' || s.lane === 'father')
  const payments = timeline?.payments ?? []

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="-ml-2 flex h-9 items-center gap-1.5 rounded-full px-2 text-sm font-bold text-navy-500 transition-colors hover:bg-navy-50 hover:text-navy-900"
      >
        <ArrowLeft className="size-4" /> Wszystkie sprawy
      </button>

      <header className="mt-2 pr-10">
        {category && <p className="text-sm font-bold text-zus-700">{category}</p>}
        <h2 className="text-2xl leading-tight font-bold tracking-tight text-navy-900">
          {result.id ? `Sprawa ${result.id}` : 'Wgrana sprawa'}
          {facts.title && <span className="font-normal text-navy-500"> · {facts.title}</span>}
        </h2>
        <p className="mt-2 flex flex-wrap items-center gap-2 text-xs font-bold">
          <span className="flex items-center gap-1.5 rounded-full bg-zus-50 px-2.5 py-1 text-zus-700">
            <span className="rounded-full bg-zus-600 px-1.5 text-[10px] font-black text-white">AI</span>
            odczytano {result.pages_read} z {result.pages} stron
          </span>
          {result.cached && (
            <span className="rounded-full bg-navy-50 px-2.5 py-1 text-navy-500">z pamięci serwera</span>
          )}
        </p>
        <p className="mt-3 leading-relaxed text-pretty text-navy-700">{facts.summary}</p>
      </header>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <Answer
          icon={ICONS.parasol}
          question="Ubezpieczenie chorobowe"
          word={insurance.covered ? 'Tak' : insurance.covered === false ? 'Nie' : 'Nie wiadomo'}
          tone={covered}
          text={insurance.text}
          pages={pagesLabel(insurance.period?.pages)}
        />
        <Answer
          icon={ICONS.koperta}
          question="Wynik a decyzja ZUS"
          word={verdict.word}
          tone={verdict.tone}
          text={comparison.text}
          pages={pagesLabel(facts.decision?.pages)}
        />
      </div>

      {result.problem && (
        <p className="mt-3 rounded-2xl bg-sun-100 px-4 py-3 text-sm leading-relaxed text-sun-700">{result.problem}</p>
      )}

      {payments.length > 0 && (
        <Section icon={ICONS.pieniadze} title="Ile wyniesie zasiłek">
          <ul className="divide-y divide-line">
            {payments.map((payment) => (
              <li key={payment.id} className="flex flex-wrap items-baseline gap-x-4 gap-y-0.5 py-2.5">
                <span className="min-w-0 flex-1 font-bold text-navy-900">{payment.title}</span>
                <span className="text-lg font-bold text-navy-900 tabular-nums">
                  {formatPln(payment.monthly)} <span className="text-sm font-normal text-navy-500">/ mies.</span>
                </span>
                <span className="w-full text-sm text-navy-500">
                  <Emphasis
                    text={`${formatRate(payment.rate)} podstawy ${formatPln(payment.base)} · razem ${formatPln(payment.total)} za ${payment.days} dni`}
                    className="text-navy-700"
                  />
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {periods.length > 0 && (
        <Section icon={ICONS.kalendarz} title="Okresy na osi">
          <ul className="divide-y divide-line">
            {periods.map((segment) => (
              <li key={segment.id} className="flex items-center gap-3 py-2">
                <Illustration src={segmentIcon(segment)} size="hint" />
                <span className="min-w-0 flex-1">
                  <span className="font-bold text-navy-900">{periodName(segment)}</span>
                  {segment.tone === 'option' && (
                    <span className="ml-2 rounded-full bg-zus-50 px-2 py-0.5 text-[11px] font-bold text-zus-700">do wyboru</span>
                  )}
                </span>
                <span className="text-sm text-navy-500 tabular-nums">
                  {formatShortDate(segment.start)} – {formatShortDate(segment.end)} · {length(segment.days)}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <section ref={factsRef} className="mt-5 rounded-3xl border border-line">
        <button
          type="button"
          onClick={() => setEditing(!editing)}
          aria-expanded={editing}
          className="flex w-full items-center gap-3 px-4 py-3 text-left sm:px-5"
        >
          <Illustration src={ICONS.zaswiadczenie} size="hint" />
          <span className="min-w-0 flex-1">
            <span className="block font-bold text-navy-900">Dane ze sprawy</span>
            <span className="block text-sm text-navy-500">
              Co AI przepisało z dokumentów. Popraw i przelicz, jeśli coś się nie zgadza.
            </span>
          </span>
          <ChevronDown className={cn('size-5 text-navy-400 transition-transform duration-200', editing && 'rotate-180')} />
        </button>
        <AnimatePresence initial={false}>
          {editing && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
              transition={{ duration: 0.25, ease: EASE_OUT }}
              className="overflow-hidden"
            >
              <div className="border-t border-line px-4 py-4 sm:px-5">
                <CaseFactsForm facts={facts} busy={busy} onRecalculate={onRecalculate} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {result.notes.length > 0 && (
        <ul className="mt-4 space-y-1 text-sm text-navy-500">
          {result.notes.map((note) => (
            <li key={note} className="flex gap-2">
              <span className="mt-[0.55em] size-1.5 shrink-0 rounded-full bg-navy-200" />
              {note}
            </li>
          ))}
        </ul>
      )}

      {error && <p className="mt-4 rounded-2xl bg-alert-50 px-4 py-3 text-sm text-alert-600">{error}</p>}

      <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={onBack}
          className="h-12 rounded-full px-5 font-bold text-navy-500 transition-colors hover:bg-navy-50 hover:text-navy-900"
        >
          Inna sprawa
        </button>
        {timeline ? (
          <PrimaryButton onClick={onShowPlan} disabled={busy} className="h-12 px-6 text-base">
            Pokaż na osi
          </PrimaryButton>
        ) : (
          <PrimaryButton onClick={openFacts} disabled={busy} className="h-12 px-6 text-base">
            Wpisz datę porodu, żeby zobaczyć oś
          </PrimaryButton>
        )}
      </div>
    </div>
  )
}

function Answer({
  icon,
  question,
  word,
  tone,
  text,
  pages,
}: {
  icon: string
  question: string
  word: string
  tone: Tone
  text: string
  pages: string | null
}) {
  return (
    <section className="rounded-3xl border border-line p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <Illustration src={icon} size="event" className="bg-navy-50/60" />
        <div className="min-w-0">
          <p className="text-sm font-bold text-navy-500">{question}</p>
          <p className={cn('text-xl leading-tight font-bold', TONE[tone])}>{word}</p>
        </div>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-navy-700">{text}</p>
      {pages && <p className="mt-1.5 text-xs font-bold text-navy-400">Źródło w aktach: {pages}</p>}
    </section>
  )
}

function Section({ icon, title, children }: { icon: string; title: string; children: ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="flex items-center gap-2 font-bold text-navy-900">
        <Illustration src={icon} size="hint" />
        {title}
      </h3>
      <div className="mt-1">{children}</div>
    </section>
  )
}
