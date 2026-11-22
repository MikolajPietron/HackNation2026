// "Jak dzielicie urlop rodzicielski?" (FUNKCJE F13 week tiles, F6 work during the leave).
// The pool is a row of week tiles: a click on a tile moves the split, the weeks that belong only
// to one parent carry a lock. Each employee can combine the leave with work up to half time,
// which lengthens it. Every move is counted by the engine as a preview (POST /api/timeline, no
// AI, nothing saved): when each parent is at home and what the leave pays a month. "Ułóż na osi"
// saves the plan (PATCH with undo); the engine refuses what the law does not allow.
//
// The numbers come from the engine, not from the screen: the pool and the weeks that belong to
// one parent are read from the timeline without a plan (the mother's share to decide and the
// father's own weeks), so the screen never restates the rule.
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { Lock, Minus, Plus } from 'lucide-react'
import { calculateTimeline } from '@/api'
import { ITEM } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import type { PlanApply } from '@/hooks/usePlanChange'
import { formatShortDate } from '@/lib/dates'
import { SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { formatPln } from '@/lib/money'
import { cn } from '@/lib/utils'
import type { ParentalPart, Role, Scenario, Timeline } from '@/types'

type Order = 'mother-first' | 'father-first' | 'together'
type Work = '1/4' | '1/3' | '1/2' | null

const ORDERS: { id: Order; label: string }[] = [
  { id: 'mother-first', label: 'Najpierw mama' },
  { id: 'father-first', label: 'Najpierw tata' },
  { id: 'together', label: 'Razem' },
]
const WORK: { id: Work; label: string }[] = [
  { id: null, label: 'bez pracy' },
  { id: '1/4', label: '¼ etatu' },
  { id: '1/3', label: '⅓ etatu' },
  { id: '1/2', label: '½ etatu' },
]

interface Plan {
  mother: number
  order: Order
  work: Record<Role, Work>
}

const weeksOf = (t: Timeline, id: string) => {
  const s = t.segments.find((x) => x.id === id)
  return s ? Math.round(s.days / 7) : 0
}

/** The parents' plan as the engine takes it. */
function partsOf(plan: Plan, pool: number): ParentalPart[] {
  const part = (parent: Role, weeks: number, withPrevious: boolean): ParentalPart => ({
    parent,
    weeks,
    start: null,
    with_previous: withPrevious,
    work_fraction: plan.work[parent],
    work_weeks: null,
  })
  const father = pool - plan.mother
  const first: Role = plan.order === 'father-first' ? 'father' : 'mother'
  const second: Role = first === 'mother' ? 'father' : 'mother'
  const weeks = { mother: plan.mother, father }
  return [part(first, weeks[first], false), part(second, weeks[second], plan.order === 'together')]
}

/** The plan already saved, read back for the editor. */
function planFrom(scenario: Scenario, defaultMother: number): Plan {
  const parts = scenario.parental_parts ?? []
  const sum = (parent: Role) => parts.filter((p) => p.parent === parent).reduce((n, p) => n + p.weeks, 0)
  const work = (parent: Role) => (parts.find((p) => p.parent === parent && p.work_fraction)?.work_fraction ?? null) as Work
  if (parts.length === 0) return { mother: defaultMother, order: 'mother-first', work: { mother: null, father: null } }
  return {
    mother: sum('mother'),
    order: parts.some((p) => p.with_previous) ? 'together' : parts[0].parent === 'father' ? 'father-first' : 'mother-first',
    work: { mother: work('mother'), father: work('father') },
  }
}

export function ParentalEditor({ scenario, onApply }: { scenario: Scenario; onApply: PlanApply }) {
  // The timeline without a plan: the pool and the weeks that are one parent's own.
  const [base, setBase] = useState<{ for: Scenario; timeline: Timeline } | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    calculateTimeline({ ...scenario, parental_parts: [] }, controller.signal)
      .then((timeline) => setBase({ for: scenario, timeline }))
      .catch(() => undefined)
    return () => controller.abort()
  }, [scenario])

  const shares = base ? { mother: weeksOf(base.timeline, 'parental'), own: weeksOf(base.timeline, 'parental-father') } : null
  if (!shares || shares.mother === 0 || shares.own === 0) return null
  return <Editor key={JSON.stringify(scenario.parental_parts)} scenario={scenario} pool={shares.mother + shares.own} own={shares.own} onApply={onApply} />
}

function Editor({ scenario, pool, own, onApply }: { scenario: Scenario; pool: number; own: number; onApply: PlanApply }) {
  const saved = useMemo(() => planFrom(scenario, pool - own), [scenario, pool, own])
  const [plan, setPlan] = useState<Plan>(saved)
  const changed = JSON.stringify(plan) !== JSON.stringify(saved) || !scenario.parental_parts?.length
  const min = own
  const max = pool - own
  const setMother = (weeks: number) => setPlan((p) => ({ ...p, mother: Math.min(max, Math.max(min, weeks)) }))
  const employee = (parent: Role) =>
    (parent === 'mother' ? (scenario.role === 'mother' ? scenario.work : scenario.mother_work) : scenario.role === 'father' ? scenario.work : scenario.father_work) === 'employment'

  // The engine counts every move (debounced): when each parent is at home, what it pays.
  const parts = useMemo(() => partsOf(plan, pool), [plan, pool])
  const [preview, setPreview] = useState<{ key: string; timeline?: Timeline; error?: string } | null>(null)
  const key = JSON.stringify(parts)
  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      calculateTimeline({ ...scenario, parental_parts: parts }, controller.signal)
        .then((timeline) => setPreview({ key, timeline }))
        .catch((error: unknown) => {
          if (!controller.signal.aborted) setPreview({ key, error: error instanceof Error ? error.message : 'Tak się nie da.' })
        })
    }, 220)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [scenario, parts, key])
  const fresh = preview?.key === key

  // The row starts with the first parent's weeks. The weeks at both ends are each parent's own
  // and never move; the split moves through the shared weeks in the middle.
  const tiles = Array.from({ length: pool }, (_, i) => {
    const motherFirst = plan.order !== 'father-first'
    const mothers = motherFirst ? i < plan.mother : i >= pool - plan.mother
    return { parent: (mothers ? 'mother' : 'father') as Role, locked: i < own || i >= pool - own }
  })
  const pick = (i: number) => setMother(plan.order === 'father-first' ? pool - i : i + 1)

  return (
    <motion.section variants={ITEM} aria-labelledby="parental-editor" className="rounded-4xl border border-line px-4 pt-5 pb-5 sm:px-5">
      <header className="flex items-start gap-3">
        <Illustration src={ICONS.wozek} size="event" className="bg-zus-50" />
        <div className="min-w-0">
          <h2 id="parental-editor" className="text-lg leading-tight font-bold text-navy-900">
            Jak dzielicie urlop rodzicielski?
          </h2>
          <p className="mt-0.5 text-sm text-navy-500">
            {pool} tygodni dla Was obojga. Po {own} tyg. należy tylko do każdego z Was <Lock className="inline size-3.5 align-[-2px]" />.
            Kliknij tydzień, żeby przesunąć podział.
          </p>
        </div>
      </header>

      {/* The pool, week by week. */}
      <div className="mt-4 flex flex-wrap gap-1" role="group" aria-label="Tygodnie urlopu rodzicielskiego">
        {tiles.map((tile, i) => (
          <button
            key={i}
            type="button"
            onClick={() => pick(i)}
            aria-label={`Tydzień ${i + 1}: ${tile.parent === 'mother' ? 'mama' : 'tata'}${tile.locked ? ', tylko dla tego rodzica' : ''}`}
            className={cn(
              'grid size-6 place-items-center rounded-md transition-[background-color,transform] duration-200 hover:scale-110 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none sm:size-[26px]',
              tile.parent === 'mother' ? 'bg-zus-600' : 'bg-navy-700',
              !tile.locked && (tile.parent === 'mother' ? 'bg-zus-400' : 'bg-navy-400'),
            )}
          >
            {tile.locked && <Lock className="size-2.5 text-white/80" strokeWidth={3} />}
          </button>
        ))}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {(['mother', 'father'] as Role[]).map((parent) => {
          const weeks = parent === 'mother' ? plan.mother : pool - plan.mother
          const step = (by: number) => setMother(plan.mother + (parent === 'mother' ? by : -by))
          return (
            <div key={parent} className="rounded-3xl bg-navy-50/50 p-3">
              <div className="flex items-center gap-3">
                <Illustration src={parent === 'mother' ? ICONS.mamaZDzieckiem : ICONS.tataZDzieckiem} size="hint" />
                <span className={cn('flex-1 font-bold', parent === 'mother' ? 'text-zus-700' : 'text-navy-700')}>
                  {parent === 'mother' ? 'Mama' : 'Tata'}
                </span>
                <Stepper label="mniej" onClick={() => step(-1)} disabled={weeks <= own}>
                  <Minus className="size-4" />
                </Stepper>
                <span className="w-16 text-center text-lg font-bold text-navy-900 tabular-nums">{weeks} tyg.</span>
                <Stepper label="więcej" onClick={() => step(1)} disabled={weeks >= pool - own}>
                  <Plus className="size-4" />
                </Stepper>
              </div>
              {employee(parent) && (
                <div className="mt-3">
                  <p className="text-xs font-bold text-navy-500">Praca w czasie urlopu (wydłuża urlop)</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5" role="radiogroup" aria-label={`Praca: ${parent === 'mother' ? 'mama' : 'tata'}`}>
                    {WORK.map((w) => {
                      const on = plan.work[parent] === w.id
                      return (
                        <button
                          key={w.label}
                          type="button"
                          role="radio"
                          aria-checked={on}
                          onClick={() => setPlan((p) => ({ ...p, work: { ...p.work, [parent]: w.id } }))}
                          className={cn(
                            'h-8 rounded-full border px-3 text-xs font-bold transition-colors duration-150',
                            on ? 'border-navy-900 bg-navy-900 text-white' : 'border-line bg-white text-navy-700 hover:border-navy-200',
                          )}
                        >
                          {w.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
        <span className="text-sm font-bold text-navy-500">Kolejność</span>
        <div role="radiogroup" aria-label="Kolejność" className="grid grid-cols-3 gap-1 rounded-full bg-navy-50 p-1 sm:inline-grid">
          {ORDERS.map((o) => {
            const on = plan.order === o.id
            return (
              <button
                key={o.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setPlan((p) => ({ ...p, order: o.id }))}
                className="relative h-9 rounded-full px-3 text-sm font-bold whitespace-nowrap"
              >
                {on && (
                  <motion.span
                    layoutId="parental-order"
                    transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                    className="absolute inset-0 rounded-full bg-white shadow-[0_1px_3px_rgb(26_36_56/0.15)]"
                  />
                )}
                <span className={cn('relative', on ? 'text-navy-900' : 'text-navy-500')}>{o.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      <Preview timeline={fresh ? preview?.timeline : undefined} error={fresh ? preview?.error : undefined} loading={!fresh} />

      <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
        {!changed && <p className="text-sm font-bold text-navy-400 sm:mr-auto">Ten podział jest na osi.</p>}
        <motion.button
          type="button"
          disabled={!changed || Boolean(fresh && preview?.error)}
          onClick={() => void onApply({ parental_parts: parts }, 'Nowy podział urlopu rodzicielskiego', 'Oś czasu pokazuje go już teraz.')}
          whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
          className="h-11 rounded-full bg-zus-600 px-6 font-bold text-white transition-colors hover:bg-zus-700 disabled:bg-navy-100 disabled:text-navy-400"
        >
          Ułóż na osi
        </motion.button>
      </div>
    </motion.section>
  )
}

/** What the engine says the split gives: each parent's leave and what it pays a month. */
function Preview({ timeline, error, loading }: { timeline?: Timeline; error?: string; loading: boolean }) {
  if (error) return <p className="mt-4 rounded-2xl bg-sun-100 px-4 py-3 text-sm font-bold text-sun-700">{error}</p>
  const line = (parent: Role) => {
    if (!timeline) return null
    const parts = timeline.segments
      .filter((s) => s.lane === parent && s.id.startsWith(`parental-${parent}-`))
      .sort((a, b) => a.start.localeCompare(b.start))
    if (parts.length === 0) return null
    const pay = timeline.payments.find((p) => p.segment_id === parts[0].id)
    return { from: parts[0].start, to: parts[parts.length - 1].end, monthly: pay?.monthly ?? null }
  }
  return (
    <div className={cn('mt-4 grid gap-2 transition-opacity duration-200 sm:grid-cols-2', loading && 'opacity-50')} aria-live="polite">
      {(['mother', 'father'] as Role[]).map((parent) => {
        const l = line(parent)
        return (
          <p key={parent} className="rounded-2xl border border-line px-4 py-2.5 text-sm">
            <span className="block text-xs font-bold text-navy-400">{parent === 'mother' ? 'Mama w domu' : 'Tata w domu'}</span>
            {l ? (
              <>
                <span className="font-bold text-navy-900 tabular-nums">
                  {formatShortDate(l.from)} – {formatShortDate(l.to)}
                </span>
                {l.monthly !== null && <span className="text-navy-500"> · {formatPln(l.monthly)} / mies.</span>}
              </>
            ) : (
              <span className="inline-block h-4 w-40 animate-pulse rounded bg-navy-100 align-middle" />
            )}
          </p>
        )
      })}
    </div>
  )
}

function Stepper({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled: boolean; children: ReactNode }) {
  return (
    <motion.button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      whileTap={disabled ? undefined : { scale: 0.92, transition: SPRING_PRESS }}
      className="grid size-9 place-items-center rounded-full border border-line bg-white text-navy-700 transition-colors hover:border-navy-200 disabled:opacity-30"
    >
      {children}
    </motion.button>
  )
}
