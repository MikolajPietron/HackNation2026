// "Raport zgodności" (FUNKCJE F37; CLAUDE.md: "zgodność z decyzjami ZUS: X/86"): the calculator's
// answer for every example case already read, set against the decision of ZUS in the case. One
// number on top, then the cases you can filter and open to see why. Reading the scans is AI
// (marked); the check and the comparison are not.
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { ArrowLeft, Check, ChevronDown, Minus, X } from 'lucide-react'
import { fetchAgreement } from '@/api'
import { Brand } from '@/components/layout/Brand'
import { ITEM, STEP } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import { EASE_OUT } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { cn } from '@/lib/utils'
import type { CaseAgreement, CaseAgreementRow, CaseOutcome, DifferenceReason } from '@/types'

type Filter = 'all' | 'agree' | 'differ' | 'undecided' | 'unread'

const OUTCOME: Record<CaseOutcome, string> = {
  granted: 'przyznano',
  refused: 'odmowa',
  partial: 'częściowo',
  unknown: '—',
}

const statusOf = (row: CaseAgreementRow): Exclude<Filter, 'all'> =>
  !row.read ? 'unread' : row.match === true ? 'agree' : row.match === false ? 'differ' : 'undecided'

const STATUS: Record<Exclude<Filter, 'all'>, { label: string; icon: ReactNode; className: string }> = {
  agree: { label: 'Zgodne z ZUS', icon: <Check className="size-4" strokeWidth={3} />, className: 'bg-zus-600 text-white' },
  differ: { label: 'Inaczej niż ZUS', icon: <X className="size-4" strokeWidth={3} />, className: 'bg-alert-600 text-white' },
  undecided: { label: 'Bez decyzji w aktach', icon: <Minus className="size-4" strokeWidth={3} />, className: 'bg-navy-100 text-navy-500' },
  unread: { label: 'Jeszcze nieprzeczytana', icon: <Minus className="size-4" strokeWidth={3} />, className: 'border-2 border-dashed border-navy-200 text-navy-300' },
}

/** Why the calculator and ZUS differ (backend/app/cases/agreement.py). */
const REASON: Record<DifferenceReason, string> = {
  reading: 'błąd odczytu sprawy',
  'missing-rule': 'brak reguły w kalkulatorze',
  'other-refusal': 'ZUS odmówił z innego powodu',
}

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'Wszystkie' },
  { id: 'agree', label: 'Zgodne' },
  { id: 'differ', label: 'Różnice' },
  { id: 'undecided', label: 'Bez decyzji' },
  { id: 'unread', label: 'Nieprzeczytane' },
]

export function ReportScreen() {
  const [report, setReport] = useState<CaseAgreement | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')

  useEffect(() => {
    fetchAgreement()
      .then(setReport)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Nie udało się wczytać raportu.'))
  }, [])

  const count = (id: Filter) => (report ? (id === 'all' ? report.rows.length : report.rows.filter((r) => statusOf(r) === id).length) : 0)
  const rows = report ? report.rows.filter((r) => filter === 'all' || statusOf(r) === filter) : []

  return (
    <div className="min-h-dvh bg-white">
      <header className="sticky top-0 z-30 flex min-h-[72px] items-center gap-4 py-2 border-b border-line bg-white/90 px-4 backdrop-blur lg:px-6">
        <Brand className="hidden sm:flex" />
        <span className="hidden h-8 w-px bg-line sm:block" />
        <div className="min-w-0 flex-1">
          <p className="text-lg leading-tight font-bold text-navy-900">Raport zgodności</p>
          <p className="text-xs text-navy-500">Kalkulator a decyzje ZUS w przykładowych sprawach</p>
        </div>
        <a
          href="/"
          className="flex h-10 items-center gap-1.5 rounded-full px-3 text-sm font-bold text-navy-500 transition-[background-color,color] duration-150 hover:bg-navy-50 hover:text-navy-900"
        >
          <ArrowLeft className="size-4" /> <span className="hidden sm:inline">Wróć do aplikacji</span>
        </a>
      </header>

      {error && <p className="mx-auto mt-10 max-w-xl rounded-3xl bg-alert-50 px-5 py-4 text-alert-600">{error}</p>}
      {!report && !error && (
        <div className="mx-auto max-w-5xl space-y-4 px-4 py-8">
          <div className="h-40 animate-pulse rounded-4xl bg-navy-50" />
          <div className="h-96 animate-pulse rounded-4xl bg-navy-50" />
        </div>
      )}

      {report && (
        <motion.main variants={STEP} initial="enter" animate="center" className="mx-auto max-w-5xl px-4 py-6 lg:py-10">
          <motion.section variants={ITEM} className="grid items-center gap-6 rounded-4xl border border-line p-5 sm:grid-cols-[auto_minmax(0,1fr)] sm:p-7">
            <Ring agree={report.agree} decided={report.decided} />
            <div className="min-w-0">
              <h1 className="text-2xl leading-tight font-bold tracking-tight text-balance text-navy-900 sm:text-3xl">
                {report.decided > 0
                  ? `Kalkulator zgadza się z ZUS w ${report.agree} z ${report.decided} spraw`
                  : 'Brak spraw z decyzją ZUS do porównania'}
              </h1>
              <p className="mt-2 text-pretty text-navy-500">
                Liczymy tylko sprawy, w których akta zawierają rozstrzygnięcie ZUS, a kalkulator potrafi
                odpowiedzieć. Przeczytane: <b className="text-navy-900">{report.read}</b> z{' '}
                <b className="text-navy-900">{report.total}</b> · z osią: {report.with_timeline} · z kwotami:{' '}
                {report.with_amounts}.
              </p>
              {Object.keys(report.reasons).length > 0 && (
                <p className="mt-3 flex flex-wrap gap-1.5 text-xs font-bold">
                  {(Object.entries(report.reasons) as [DifferenceReason, number][]).map(([reason, n]) => (
                    <span key={reason} className="rounded-full bg-alert-50 px-2.5 py-1 text-alert-600">
                      {REASON[reason]}: {n}
                    </span>
                  ))}
                </p>
              )}
              <p className="mt-3 flex items-start gap-2 rounded-2xl bg-navy-50/60 px-3 py-2 text-sm text-navy-700">
                <span className="mt-0.5 shrink-0 rounded-full bg-zus-600 px-1.5 text-[10px] font-black text-white">AI</span>
                Dane ze skanów przepisuje AI, z numerami stron. Sprawdzenie ubezpieczenia i porównanie z
                decyzją robi kalkulator reguł, bez AI.
              </p>
            </div>
          </motion.section>

          <motion.div variants={ITEM} className="scrollbar-none -mx-4 mt-6 flex gap-2 overflow-x-auto px-4">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                aria-pressed={filter === f.id}
                className={cn(
                  'flex h-10 shrink-0 items-center gap-2 rounded-full border px-4 text-sm font-bold transition-colors duration-150',
                  filter === f.id ? 'border-navy-900 bg-navy-900 text-white' : 'border-line bg-white text-navy-700 hover:border-navy-200',
                )}
              >
                {f.label}
                <span className={cn('rounded-full px-1.5 text-xs', filter === f.id ? 'bg-white/20' : 'bg-navy-50 text-navy-500')}>
                  {count(f.id)}
                </span>
              </button>
            ))}
          </motion.div>

          <motion.ul variants={ITEM} className="mt-4 divide-y divide-line rounded-4xl border border-line">
            {rows.length === 0 && <li className="px-5 py-10 text-center text-navy-500">Brak spraw w tym widoku.</li>}
            {rows.map((row) => (
              <Row key={row.id} row={row} />
            ))}
          </motion.ul>
        </motion.main>
      )}
    </div>
  )
}

/** The agreement as a ring: green share of the cases with a decision of ZUS. */
function Ring({ agree, decided }: { agree: number; decided: number }) {
  const reduce = useReducedMotion()
  const size = 132
  const stroke = 12
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const share = decided > 0 ? agree / decided : 0
  return (
    <div className="relative mx-auto size-[132px] shrink-0">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--color-navy-50)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-zus-600)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - share) }}
          transition={reduce ? { duration: 0 } : { duration: 1, ease: EASE_OUT, delay: 0.2 }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <p className="text-3xl font-bold text-navy-900 tabular-nums">
            {agree}
            <span className="text-lg text-navy-400">/{decided}</span>
          </p>
          <p className="text-xs font-bold text-navy-500">zgodnych</p>
        </div>
      </div>
    </div>
  )
}

function Row({ row }: { row: CaseAgreementRow }) {
  const [open, setOpen] = useState(false)
  const status = STATUS[statusOf(row)]
  const expandable = row.read
  return (
    <li>
      <button
        type="button"
        onClick={() => expandable && setOpen(!open)}
        aria-expanded={expandable ? open : undefined}
        disabled={!expandable}
        className={cn(
          'flex w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-150 sm:px-5',
          expandable ? 'hover:bg-navy-50/50' : 'cursor-default',
        )}
      >
        <span className={cn('grid size-8 shrink-0 place-items-center rounded-full', status.className)} title={status.label}>
          {status.icon}
        </span>
        <span className="w-10 shrink-0 text-sm font-black text-navy-400">{row.id}</span>
        <span className="min-w-0 flex-1">
          <span className={cn('block font-bold', row.read ? 'text-navy-900' : 'text-navy-400')}>
            {row.title || row.category}
          </span>
          <span className="block text-sm text-navy-500">
            {row.read ? (row.title ? row.category : status.label) : status.label}
          </span>
        </span>
        {row.read && (
          <span className="hidden shrink-0 items-center gap-1.5 text-xs font-bold sm:flex">
            <Outcome who="ZUS" outcome={row.zus ?? 'unknown'} />
            <Outcome who="Kalkulator" outcome={row.ours ?? 'unknown'} />
          </span>
        )}
        {expandable && (
          <ChevronDown className={cn('size-5 shrink-0 text-navy-300 transition-transform duration-200', open && 'rotate-180')} />
        )}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <div className="space-y-3 px-4 pb-4 sm:pr-5 sm:pl-[104px]">
              <div className="flex flex-wrap gap-1.5 text-xs font-bold sm:hidden">
                <Outcome who="ZUS" outcome={row.zus ?? 'unknown'} />
                <Outcome who="Kalkulator" outcome={row.ours ?? 'unknown'} />
              </div>
              {row.reason && (
                <p className="text-sm font-bold text-alert-600">Powód różnicy: {REASON[row.reason]}</p>
              )}
              {row.reason_text && <Detail icon={ICONS.koperta} title="Kalkulator a decyzja ZUS" text={row.reason_text} />}
              {row.covered !== null && (
                <Detail
                  icon={ICONS.parasol}
                  title="Ubezpieczenie chorobowe"
                  text={row.covered ? 'Kalkulator: ubezpieczenie w dniu powstania prawa.' : 'Kalkulator: brak ubezpieczenia w dniu powstania prawa.'}
                />
              )}
              {row.problem && <Detail icon={ICONS.kalendarz} title="Oś" text={row.problem} />}
              {!row.problem && (
                <p className="text-sm text-navy-500">
                  Oś: {row.timeline ? 'jest' : 'brak'} · kwoty: {row.payments > 0 ? `${row.payments} okresy` : 'brak danych o zarobkach'}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  )
}

function Outcome({ who, outcome }: { who: string; outcome: CaseOutcome }) {
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5',
        outcome === 'granted' ? 'bg-zus-50 text-zus-700' : outcome === 'refused' ? 'bg-alert-50 text-alert-600' : 'bg-navy-50 text-navy-500',
      )}
    >
      {who}: {OUTCOME[outcome]}
    </span>
  )
}

function Detail({ icon, title, text }: { icon: string; title: string; text: string }) {
  return (
    <div className="flex gap-3">
      <Illustration src={icon} size="hint" />
      <div className="min-w-0">
        <p className="text-sm font-bold text-navy-900">{title}</p>
        <p className="text-sm leading-relaxed text-navy-700">{text}</p>
      </div>
    </div>
  )
}
