// "Plany dla Was" (FUNKCJE F8): the family says what it cares about, the engine proposes 2-3
// plans for that goal (POST /api/plans, no AI), each counted on the whole timeline. A card shows
// the plan's figures (the engine's: the screen adds nothing up), what the family gives up with
// it, and applies it with one click (PATCH of the plan's `patch`, with undo).
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Check, ChevronDown, LoaderCircle } from 'lucide-react'
import { proposePlans } from '@/api'
import { ITEM } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import type { PlanApply } from '@/hooks/usePlanChange'
import { formatShortDate } from '@/lib/dates'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { formatPln } from '@/lib/money'
import { cn } from '@/lib/utils'
import type { Plan, PlanFigures, PlanGoal, PlansResult, Scenario } from '@/types'

const GOALS: { id: PlanGoal; label: string; icon: string }[] = [
  { id: 'most-money', label: 'Najwięcej pieniędzy', icon: ICONS.skarbonka },
  { id: 'longest-home', label: 'Najdłużej w domu', icon: ICONS.dom },
  { id: 'equal-split', label: 'Równy podział', icon: ICONS.waga },
  { id: 'quick-return', label: 'Szybki powrót do pracy', icon: ICONS.etat },
]

/** The last answer, and what it was asked for: a different scenario or goal means loading. */
interface Answer {
  scenario: Scenario | null
  goal: PlanGoal | null
  result?: PlansResult
  error?: string
}

export function GoalPlans({
  scenario,
  onApply,
}: {
  scenario: Scenario | null
  /** Applies a plan; while the assistant writes it says to wait. */
  onApply: PlanApply
}) {
  const [goal, setGoal] = useState<PlanGoal>('most-money')
  const [answer, setAnswer] = useState<Answer>({ scenario: null, goal: null })
  const loading = answer.scenario !== scenario || answer.goal !== goal

  // Plans for the goal, again whenever the plan changes (an applied plan becomes "Tak macie teraz").
  useEffect(() => {
    if (!scenario) return
    const controller = new AbortController()
    proposePlans(scenario, goal, controller.signal)
      .then((result) => setAnswer({ scenario, goal, result }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setAnswer((a) => ({
          scenario,
          goal,
          result: a.result,
          error: error instanceof Error ? error.message : 'Nie udało się ułożyć planów.',
        }))
      })
    return () => controller.abort()
  }, [scenario, goal])

  const result = answer.result
  if (!scenario || result?.sensitive) return null
  return (
    <motion.section variants={ITEM} className="mt-10 lg:mt-12" aria-labelledby="goal-plans">
      <h2 id="goal-plans" className="text-2xl leading-tight font-bold tracking-tight text-navy-900">
        Plany dla Was
      </h2>
      <p className="mt-1 text-navy-500">Na czym Wam zależy? Policzymy plany na całej osi i pokażemy różnice.</p>

      <div role="radiogroup" aria-label="Na czym Wam zależy?" className="scrollbar-none -mx-4 mt-4 flex gap-2 overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-wrap lg:px-0">
        {GOALS.map((g) => {
          const on = goal === g.id
          return (
            <motion.button
              key={g.id}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => setGoal(g.id)}
              whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
              className={cn(
                'flex h-12 shrink-0 items-center gap-2 rounded-full border pr-4 pl-1.5 text-sm font-bold transition-[border-color,background-color,color] duration-150',
                'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                on ? 'border-zus-600 bg-zus-50 text-zus-900' : 'border-line text-navy-700 hover:border-navy-200',
              )}
            >
              <Illustration src={g.icon} size="hint" />
              {g.label}
            </motion.button>
          )
        })}
      </div>

      {!loading && answer.error && (
        <p role="alert" className="mt-4 rounded-2xl bg-alert-50 px-4 py-3 text-sm font-bold text-alert-600">
          {answer.error}
        </p>
      )}
      {result?.reason && <p className="mt-4 text-navy-500">{result.reason}</p>}

      <div className={cn('relative mt-4 transition-opacity duration-200', loading && result && 'opacity-60')}>
        {!result && loading && (
          <div className="grid gap-3 sm:grid-cols-3 sm:gap-4" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-72 animate-pulse rounded-3xl bg-navy-50/70" />
            ))}
          </div>
        )}
        {result && (
          <div className="grid gap-3 sm:grid-cols-3 sm:gap-4">
            <AnimatePresence mode="popLayout" initial={false}>
              {result.plans.map((plan, index) => (
                <PlanCard
                  key={`${result.goal}-${plan.id}`}
                  plan={plan}
                  index={index}
                  goal={result.goal}
                  onApply={() =>
                    void onApply(plan.patch, `Plan: ${plan.title}`, 'Oś czasu pokazuje teraz ten plan.')
                  }
                />
              ))}
            </AnimatePresence>
          </div>
        )}
        {loading && result && (
          <LoaderCircle className="absolute top-3 right-3 size-5 animate-spin text-navy-400" aria-label="Liczę plany" />
        )}
      </div>

      {result && result.notes.length > 0 && <HowCounted notes={result.notes} />}
    </motion.section>
  )
}

/** The figure a goal is about, first and big. */
function headline(goal: PlanGoal, f: PlanFigures): { label: string; value: string } | null {
  switch (goal) {
    case 'most-money':
      return f.total !== null ? { label: 'Zasiłki razem', value: formatPln(f.total) } : null
    case 'longest-home':
      return f.home_until ? { label: 'Dziecko z rodzicem w domu do', value: formatShortDate(f.home_until) } : null
    case 'equal-split':
      return { label: 'Urlopy mamy i taty', value: `${f.mother.leave_days} i ${f.father.leave_days} dni` }
    case 'quick-return':
      return f.mother.back_to_work ? { label: 'Mama wraca do pracy', value: formatShortDate(f.mother.back_to_work) } : null
  }
}

function PlanCard({
  plan,
  index,
  goal,
  onApply,
}: {
  plan: Plan
  index: number
  goal: PlanGoal
  onApply: () => void
}) {
  const f = plan.figures
  const big = headline(goal, f)
  const best = plan.rank === 1
  const days = f.mother.leave_days + f.father.leave_days
  const rows = [
    goal !== 'most-money' && f.total !== null && { label: 'Zasiłki razem', value: formatPln(f.total) },
    goal !== 'longest-home' && f.home_until && { label: 'W domu do', value: formatShortDate(f.home_until) },
    goal !== 'quick-return' && f.mother.back_to_work && { label: 'Mama wraca', value: formatShortDate(f.mother.back_to_work) },
  ].filter(Boolean) as { label: string; value: string }[]

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.3, delay: index * 0.05, ease: EASE_OUT } }}
      exit={{ opacity: 0, transition: { duration: 0.12 } }}
      className={cn(
        'flex flex-col rounded-3xl border p-5',
        best ? 'border-zus-600 shadow-[0_0_0_1px_var(--color-zus-600)]' : 'border-line',
      )}
    >
      <div className="flex min-h-6 flex-wrap items-center gap-2">
        {best && <span className="rounded-full bg-zus-600 px-2.5 py-0.5 text-[11px] font-bold text-white">najlepszy dla celu</span>}
        {plan.current && <span className="rounded-full bg-navy-50 px-2.5 py-0.5 text-[11px] font-bold text-navy-700">tak macie teraz</span>}
      </div>
      <h3 className="mt-2 text-lg leading-snug font-bold text-navy-900">{plan.title}</h3>

      {big && (
        <div className="mt-3">
          <p className="text-xs font-bold text-navy-400">{big.label}</p>
          <p className="text-2xl font-bold tracking-tight text-navy-900 tabular-nums">{big.value}</p>
        </div>
      )}

      {/* Who is at home, as a share of the days of leave. */}
      {days > 0 && (
        <div className="mt-3">
          <div className="flex h-2.5 overflow-hidden rounded-full bg-navy-50" aria-hidden>
            <span className="bg-zus-600" style={{ width: `${(f.mother.leave_days / days) * 100}%` }} />
            <span className="ml-0.5 bg-navy-700" style={{ width: `${(f.father.leave_days / days) * 100}%` }} />
          </div>
          <p className="mt-1.5 flex justify-between text-xs font-bold">
            <span className="text-zus-700">Mama {f.mother.leave_days} dni</span>
            <span className="text-navy-700">Tata {f.father.leave_days} dni</span>
          </p>
        </div>
      )}

      {rows.length > 0 && (
        <dl className="mt-3 space-y-1 text-sm">
          {rows.map((row) => (
            <div key={row.label} className="flex items-baseline justify-between gap-3">
              <dt className="text-navy-500">{row.label}</dt>
              <dd className="text-right font-bold text-navy-900 tabular-nums">{row.value}</dd>
            </div>
          ))}
        </dl>
      )}

      <p className="mt-3 line-clamp-4 text-sm leading-relaxed text-navy-500">{plan.summary}</p>

      {plan.given_up.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {plan.given_up.map((line) => (
            <li key={line} className="flex gap-2 text-sun-700">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-sun-400" />
              {line}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto pt-4">
        {plan.current ? (
          <p className="flex h-10 items-center justify-center gap-1.5 rounded-full bg-navy-50 text-sm font-bold text-navy-500">
            <Check className="size-4" /> Na osi
          </p>
        ) : (
          <motion.button
            type="button"
            onClick={onApply}
            whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
            className={cn(
              'h-10 w-full rounded-full text-sm font-bold transition-colors duration-200 disabled:opacity-50',
              best ? 'bg-zus-600 text-white hover:bg-zus-700' : 'border border-line text-navy-900 hover:bg-navy-50',
            )}
          >
            Ułóż na osi
          </motion.button>
        )}
      </div>
    </motion.article>
  )
}

function HowCounted({ notes }: { notes: string[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-4">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-sm font-bold text-zus-700"
      >
        Jak liczymy plany
        <ChevronDown className={cn('size-4 transition-transform duration-200', open && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
            transition={{ duration: 0.22, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            {notes.map((note) => (
              <li key={note} className="pt-2 text-sm leading-relaxed text-navy-500">
                {note}
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  )
}
