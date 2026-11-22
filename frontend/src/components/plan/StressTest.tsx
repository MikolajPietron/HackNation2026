// "Co, jeśli coś pójdzie inaczej?" (FUNKCJE F11): the plan tested against every event that can
// still happen (POST /api/stress, no AI). Each event says whether the family keeps its rights,
// faces a new risk or loses something, with the engine's own lines and the dates it assumed.
// Nothing is saved: it is a preview. The mother's illness, stay in hospital or death are behind
// their own toggle and worded gently (the engine marks them `sensitive`).
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { ChevronDown } from 'lucide-react'
import { stressTest } from '@/api'
import { ITEM } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import { EASE_OUT } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { formatPln } from '@/lib/money'
import { cn } from '@/lib/utils'
import type { Scenario, StressEvent, StressEventId, StressReport, StressVerdict } from '@/types'

const ICON: Record<StressEventId, string> = {
  premature: ICONS.inkubator,
  twins: ICONS.blizniaki,
  'job-loss-bankruptcy': ICONS.karton,
  'job-loss-liquidation': ICONS.karton,
  'job-loss-employer-death': ICONS.karton,
  'job-loss-unlawful': ICONS.karton,
  'job-loss-other': ICONS.karton,
  'mother-incapacity': ICONS.szpital,
  'mother-hospital': ICONS.szpital,
  'mother-death': ICONS.serce,
  'father-takeover': ICONS.tataZDzieckiem,
  'za-zyciem': ICONS.serce,
}

const VERDICT: Record<StressVerdict, { label: string; chip: string }> = {
  kept: { label: 'prawa zostają', chip: 'bg-zus-50 text-zus-700' },
  risk: { label: 'ryzyko', chip: 'bg-sun-100 text-sun-700' },
  loss: { label: 'coś przepada', chip: 'bg-sun-100 text-sun-700 ring-1 ring-sun-300' },
}

interface Answer {
  scenario: Scenario | null
  report?: StressReport
  error?: string
}

export function StressTest({
  scenario,
  focus,
}: {
  scenario: Scenario | null
  /** Open these events (e.g. from the "Co jeśli…" chip), with a counter so a repeat click works. */
  focus: { ids: StressEventId[]; n: number } | null
}) {
  const [answer, setAnswer] = useState<Answer>({ scenario: null })
  const [open, setOpen] = useState<Set<StressEventId>>(new Set())
  const [gentleOpen, setGentleOpen] = useState(false)
  const section = useRef<HTMLElement>(null)
  const reduce = useReducedMotion()

  useEffect(() => {
    if (!scenario) return
    const controller = new AbortController()
    stressTest(scenario, false, controller.signal)
      .then((report) => setAnswer({ scenario, report }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setAnswer({ scenario, error: error instanceof Error ? error.message : 'Nie udało się sprawdzić planu.' })
      })
    return () => controller.abort()
  }, [scenario])

  // A chip asked for an event: open it and bring the card into view.
  const [seen, setSeen] = useState(0)
  if (focus && focus.n !== seen) {
    setSeen(focus.n)
    setOpen((current) => new Set([...current, ...focus.ids]))
  }
  useEffect(() => {
    if (!focus) return
    const timer = window.setTimeout(
      () => section.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }),
      80,
    )
    return () => window.clearTimeout(timer)
  }, [focus, reduce])

  const report = answer.report
  if (!scenario || report?.sensitive) return null
  const events = report?.events ?? []
  const plain = events.filter((e) => !e.sensitive)
  const gentle = events.filter((e) => e.sensitive)
  const count = (verdict: StressVerdict) => plain.filter((e) => e.verdict === verdict).length
  const toggle = (id: StressEventId) =>
    setOpen((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <motion.section
      ref={section}
      variants={ITEM}
      aria-labelledby="stress-test"
      className="mt-10 scroll-mt-4 rounded-4xl border border-line px-4 pt-5 pb-3 sm:px-5 lg:mt-12"
    >
      <header className="flex items-start gap-3">
        <Illustration src={ICONS.parasol} size="event" className="bg-navy-50/70" />
        <div className="min-w-0">
          <h2 id="stress-test" className="text-lg leading-tight font-bold text-navy-900">
            Co, jeśli coś pójdzie inaczej?
          </h2>
          <p className="mt-0.5 text-sm text-navy-500">
            {report && plain.length > 0
              ? summary(count('kept'), count('risk'), count('loss'))
              : 'Sprawdzamy Wasz plan na zdarzeniach, które jeszcze mogą się zdarzyć.'}
          </p>
        </div>
      </header>

      {answer.error && (
        <p role="alert" className="mt-4 rounded-2xl bg-alert-50 px-4 py-3 text-sm font-bold text-alert-600">
          {answer.error}
        </p>
      )}
      {!report && !answer.error && (
        <div className="mt-4 space-y-2" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-14 animate-pulse rounded-2xl bg-navy-50/70" />
          ))}
        </div>
      )}
      {report?.reason && <p className="mt-4 text-sm text-navy-500">{report.reason}</p>}

      {plain.length > 0 && (
        <ul className="mt-3 divide-y divide-line">
          {plain.map((event) => (
            <EventRow key={event.id} event={event} open={open.has(event.id)} onToggle={() => toggle(event.id)} />
          ))}
        </ul>
      )}

      {gentle.length > 0 && (
        <div className="border-t border-line pt-1">
          <button
            type="button"
            onClick={() => setGentleOpen((o) => !o)}
            aria-expanded={gentleOpen}
            className="flex w-full items-center gap-2 rounded-2xl px-2 py-3 text-left text-sm font-bold text-navy-500 transition-colors hover:bg-navy-50/60"
          >
            <span className="flex-1">Trudne sytuacje mamy: choroba, szpital ({gentle.length})</span>
            <ChevronDown className={cn('size-4 transition-transform duration-200', gentleOpen && 'rotate-180')} />
          </button>
          <AnimatePresence initial={false}>
            {gentleOpen && (
              <motion.ul
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
                transition={{ duration: 0.24, ease: EASE_OUT }}
                className="divide-y divide-line overflow-hidden"
              >
                <li className="px-2 pb-2 text-sm text-navy-500">
                  Co dzieje się z urlopem, gdy mama nie może opiekować się dzieckiem. Tata może wtedy
                  przejąć urlop macierzyński.
                </li>
                {gentle.map((event) => (
                  <EventRow
                    key={event.id}
                    event={event}
                    open={open.has(event.id)}
                    onToggle={() => toggle(event.id)}
                    gentle
                  />
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </div>
      )}
    </motion.section>
  )
}

/** "8 zdarzeń nic Wam nie zabiera, 1 niesie ryzyko, 1 coś zabiera." */
function summary(kept: number, risk: number, loss: number): string {
  // 2-4 take the plural verb; 1 and 5+ the singular ("5 zdarzeń niesie").
  const few = (n: number) => n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)
  const parts = []
  if (kept) {
    const noun = kept === 1 ? 'zdarzenie' : few(kept) ? 'zdarzenia' : 'zdarzeń'
    parts.push(`${kept} ${noun} nic Wam nie ${few(kept) ? 'zabierają' : 'zabiera'}`)
  }
  if (risk) parts.push(`${risk} ${few(risk) ? 'niosą' : 'niesie'} ryzyko`)
  if (loss) parts.push(`${loss} coś ${few(loss) ? 'zabierają' : 'zabiera'}`)
  return `${parts.join(', ')}. Kliknij zdarzenie, żeby zobaczyć, co się zmieni.`
}

function EventRow({
  event,
  open,
  onToggle,
  gentle = false,
}: {
  event: StressEvent
  open: boolean
  onToggle: () => void
  gentle?: boolean
}) {
  const verdict = VERDICT[event.verdict]
  const diff = event.money?.diff ?? null
  return (
    <li>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="group flex w-full items-center gap-3 rounded-2xl px-2 py-2.5 text-left transition-colors duration-150 hover:bg-navy-50/60 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
      >
        <Illustration src={ICON[event.id]} size="event" className="bg-white" />
        <span className="min-w-0 flex-1">
          <span className="block font-bold text-navy-900">{event.title}</span>
          {!gentle && (
            <span className="mt-0.5 flex flex-wrap items-center gap-2 text-xs font-bold">
              <span className={cn('rounded-full px-2 py-0.5', verdict.chip)}>{verdict.label}</span>
              {diff !== null && diff !== 0 && (
                <span className={cn('tabular-nums', diff > 0 ? 'text-zus-700' : 'text-sun-700')}>
                  {diff > 0 ? '+' : '−'}
                  {formatPln(Math.abs(diff))}
                </span>
              )}
            </span>
          )}
        </span>
        <ChevronDown
          className={cn('size-4 shrink-0 text-navy-300 transition-transform duration-200 group-hover:text-navy-500', open && 'rotate-180')}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
            transition={{ duration: 0.24, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <div className="pb-4 pl-14 pr-2 text-sm">
              {event.plan_breaks && (
                <p className="mb-2 rounded-2xl bg-sun-100 px-3 py-2 font-bold text-sun-700">{event.plan_breaks}</p>
              )}
              <ul className="space-y-1.5">
                {event.lines.map((line) => (
                  <li key={line} className="flex gap-2 text-navy-900">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-navy-300" />
                    {line}
                  </li>
                ))}
              </ul>
              {event.risks.map((risk) => (
                <p key={risk.id} className="mt-3 rounded-2xl bg-sun-100/70 px-3 py-2 text-sun-700">
                  <b className="text-navy-900">{risk.title}.</b> {risk.text}
                </p>
              ))}
              {event.assumed.length > 0 && (
                <p className="mt-3 text-xs leading-relaxed text-navy-400">{event.assumed.join(' ')}</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  )
}
