// "Jak dzielicie urlop rodzicielski?" (FUNKCJE F13 the pool to split, F6 work during the leave).
// One decision on top: how many weeks each parent takes, on a slider over a thin bar of the
// pool's weeks (each parent's own weeks are the darker ends), with three quick splits. Under it
// the engine's answer in one line per parent: when at home and what it pays a month. The order
// (one after the other or together) and part-time work are behind "Więcej możliwości". Every
// move is counted by the engine as a preview (POST /api/timeline, no AI, nothing saved); "Ułóż
// na osi" saves the plan (PATCH with undo), and the engine refuses what the law does not allow.
//
// The numbers come from the engine, not from the screen: the pool and the weeks that belong to
// one parent are read from the timeline without a plan (the mother's share to decide and the
// father's own weeks), so the screen never restates the rule.
import { useEffect, useId, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, Lock } from 'lucide-react'
import { calculateTimeline } from '@/api'
import { ITEM } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import { TextStates } from '@/components/ui/text-states'
import type { PlanApply } from '@/hooks/usePlanChange'
import { formatShortDate } from '@/lib/dates'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { formatPlnShort } from '@/lib/money'
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
  const [more, setMore] = useState(false)
  const changed = JSON.stringify(plan) !== JSON.stringify(saved) || !scenario.parental_parts?.length
  const min = own
  const max = pool - own
  const father = pool - plan.mother
  const setMother = (weeks: number) => setPlan((p) => ({ ...p, mother: Math.min(max, Math.max(min, weeks)) }))
  const employee = (parent: Role) =>
    (parent === 'mother' ? (scenario.role === 'mother' ? scenario.work : scenario.mother_work) : scenario.role === 'father' ? scenario.work : scenario.father_work) === 'employment'
  const workers = (['mother', 'father'] as Role[]).filter(employee)

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

  const presets = [
    { label: 'Głównie mama', mother: max },
    { label: 'Po równo', mother: Math.ceil(pool / 2) },
    { label: 'Głównie tata', mother: min },
  ]
  // What "Więcej możliwości" holds, said in a few words while it is closed.
  const extras = [
    plan.order === 'father-first' ? 'najpierw tata' : plan.order === 'together' ? 'razem' : null,
    ...workers.filter((r) => plan.work[r]).map((r) => `${r === 'mother' ? 'mama' : 'tata'} pracuje na ${WORK.find((w) => w.id === plan.work[r])!.label}`),
  ].filter(Boolean)

  return (
    <motion.section variants={ITEM} aria-labelledby="parental-editor" className="rounded-4xl border border-line px-4 pt-5 pb-5 sm:px-6">
      <header className="flex items-start gap-3">
        <Illustration src={ICONS.wozek} size="event" className="bg-zus-50" />
        <div className="min-w-0">
          <h2 id="parental-editor" className="text-lg leading-tight font-bold text-navy-900">
            Jak dzielicie urlop rodzicielski?
          </h2>
          <p className="mt-0.5 text-sm text-navy-500">
            {pool} tygodni dla Was obojga. Każde z Was ma {own} tygodni tylko dla siebie.
          </p>
        </div>
      </header>

      {/* The split. */}
      <div className="mt-6 flex items-end justify-between gap-4">
        <Share who="Mama" weeks={plan.mother} tone="text-zus-700" />
        <Share who="Tata" weeks={father} tone="text-navy-700" align="right" />
      </div>
      <Split pool={pool} own={own} mother={plan.mother} min={min} max={max} onChange={setMother} />

      <div className="mt-4 sm:max-w-md">
        <Segmented
          label="Szybki podział"
          options={presets.map((p) => ({ id: p.mother, label: p.label }))}
          value={presets.some((p) => p.mother === plan.mother) ? plan.mother : null}
          onChange={(weeks) => weeks !== null && setMother(weeks)}
        />
      </div>

      <Preview timeline={fresh ? preview?.timeline : undefined} error={fresh ? preview?.error : undefined} loading={!fresh} />

      {/* The rest, on demand. */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setMore((m) => !m)}
          aria-expanded={more}
          className="flex items-center gap-1.5 text-sm font-bold text-zus-700 hover:text-zus-900"
        >
          Więcej możliwości
          <ChevronDown className={cn('size-4 transition-transform duration-200', more && 'rotate-180')} />
          {!more && extras.length > 0 && <span className="font-normal text-navy-500">· {extras.join(', ')}</span>}
        </button>
        <AnimatePresence initial={false}>
          {more && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
              transition={{ duration: 0.24, ease: EASE_OUT }}
              className="overflow-hidden"
            >
              <div className="space-y-4 pt-4">
                <Field label="Kolejność">
                  <Segmented label="Kolejność" options={ORDERS} value={plan.order} onChange={(order) => order && setPlan((p) => ({ ...p, order }))} />
                </Field>
                {workers.map((parent) => {
                  const label = `${parent === 'mother' ? 'Mama' : 'Tata'}: praca w czasie urlopu (wydłuża urlop)`
                  return (
                    <Field key={parent} label={label}>
                      <Segmented
                        label={label}
                        options={WORK.map((w) => ({ id: w.id, label: w.label }))}
                        value={plan.work[parent]}
                        onChange={(work) => setPlan((p) => ({ ...p, work: { ...p.work, [parent]: work } }))}
                      />
                    </Field>
                  )
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
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

/** One parent's share, big. */
function Share({ who, weeks, tone, align = 'left' }: { who: string; weeks: number; tone: string; align?: 'left' | 'right' }) {
  return (
    <p className={cn('flex flex-col', align === 'right' && 'items-end text-right')}>
      <span className={cn('text-sm font-bold', tone)}>{who}</span>
      <span className="text-[28px] leading-none font-bold tracking-tight text-navy-900 tabular-nums">
        <TextStates text={`${weeks} tyg.`} />
      </span>
    </p>
  )
}

/**
 * The pool as one thin bar of weeks, the mother's from the left and the father's from the right;
 * the darker ends are each parent's own weeks. A slider on top moves the split (arrow keys work).
 */
function Split({
  pool,
  own,
  mother,
  min,
  max,
  onChange,
}: {
  pool: number
  own: number
  mother: number
  min: number
  max: number
  onChange: (weeks: number) => void
}) {
  return (
    <div className="relative mt-3 py-2">
      <div className="flex h-3 gap-[2px]" aria-hidden>
        {Array.from({ length: pool }, (_, i) => {
          const mothers = i < mother
          const ownWeek = i < own || i >= pool - own
          return (
            <span
              key={i}
              className={cn(
                'flex-1 transition-colors duration-200 first:rounded-l-full last:rounded-r-full',
                mothers ? (ownWeek ? 'bg-zus-600' : 'bg-zus-400') : ownWeek ? 'bg-navy-700' : 'bg-navy-400',
              )}
            />
          )
        })}
      </div>
      {/* Only the part of the pool that can move is the slider's range. */}
      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={mother}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label="Tygodnie mamy"
        aria-valuetext={`Mama ${mother} tygodni, tata ${pool - mother} tygodni`}
        className={cn(
          'absolute top-0 h-7 cursor-pointer appearance-none bg-transparent',
          '[&::-webkit-slider-thumb]:size-7 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-navy-900 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-[0_4px_12px_-4px_rgb(26_36_56/0.5)]',
          '[&::-moz-range-thumb]:size-7 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-navy-900 [&::-moz-range-thumb]:bg-white',
          'focus-visible:outline-none [&:focus-visible::-webkit-slider-thumb]:ring-4 [&:focus-visible::-webkit-slider-thumb]:ring-zus-400/50',
        )}
        // The thumb sits on the split between the weeks: the range spans the movable weeks.
        style={{ left: `calc(${(min / pool) * 100}% - 14px)`, width: `calc(${((max - min) / pool) * 100}% + 28px)` }}
      />
      <div className="mt-2 flex justify-between text-xs text-navy-500">
        <span>
          <Lock className="mr-1 inline size-3 align-[-1px]" />
          {own} tyg. tylko mamy
        </span>
        <span>
          {own} tyg. tylko taty
          <Lock className="ml-1 inline size-3 align-[-1px]" />
        </span>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="sm:max-w-md">
      <p className="mb-1.5 text-sm font-bold text-navy-700">{label}</p>
      {children}
    </div>
  )
}

/** One choice of a few, in one row on any screen: the chosen one slides under the label. */
function Segmented<T extends string | number | null>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { id: T; label: string }[]
  value: T | null
  onChange: (value: T) => void
}) {
  const id = useId()
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="grid gap-1 rounded-full bg-navy-50 p-1"
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      {options.map((option) => {
        const on = value === option.id
        return (
          <button
            key={option.label}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(option.id)}
            className="relative h-9 rounded-full px-1 text-[13px] font-bold whitespace-nowrap sm:text-sm"
          >
            {on && (
              <motion.span
                layoutId={`segment-${id}`}
                transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                className="absolute inset-0 rounded-full bg-white shadow-[0_1px_3px_rgb(26_36_56/0.15)]"
              />
            )}
            <span className={cn('relative', on ? 'text-navy-900' : 'text-navy-500')}>{option.label}</span>
          </button>
        )
      })}
    </div>
  )
}

/** What the engine says the split gives, one line per parent: when at home, what it pays. */
function Preview({ timeline, error, loading }: { timeline?: Timeline; error?: string; loading: boolean }) {
  if (error) return <p className="mt-5 rounded-2xl bg-sun-100 px-4 py-3 text-sm font-bold text-sun-700">{error}</p>
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
    <dl className={cn('mt-5 divide-y divide-line rounded-2xl bg-navy-50/50 px-4 transition-opacity duration-200', loading && 'opacity-50')} aria-live="polite">
      {(['mother', 'father'] as Role[]).map((parent) => {
        const l = line(parent)
        return (
          <div key={parent} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 py-3">
            <dt className="text-sm font-bold text-navy-500">{parent === 'mother' ? 'Mama w domu' : 'Tata w domu'}</dt>
            <dd className="text-[15px] font-bold text-navy-900 tabular-nums">
              {l ? (
                <>
                  {formatShortDate(l.from)} – {formatShortDate(l.to)}
                  {l.monthly !== null && <span className="font-normal text-navy-500"> · {formatPlnShort(l.monthly)} / mies.</span>}
                </>
              ) : (
                <span className="inline-block h-4 w-44 animate-pulse rounded bg-navy-100 align-middle" />
              )}
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
