// "Na co uważać" (FUNKCJE F26, the brief's point h): what can take the benefit away or lower it,
// from the guide's section H (pp. 9–10) and the contribution debt (ustawa art. 2a). The status of
// each line is the engine's: when the engine has a point about it (the insurance on the day of the
// birth, the debt, a contract "dla pozoru", a raised contribution base) the line says what that
// point says and opens it in "Dlaczego tak?". Otherwise the line shows the source's own words,
// quoted from the engine's parameters: the screen adds no rule of its own.
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { fetchAdminParams } from '@/api'
import { ITEM } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import { EASE_OUT } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { CaseNote, Scenario, SourceRef, Timeline } from '@/types'

type Level = 'risk' | 'check' | 'ok' | 'info'

const LEVEL: Record<Level, { label: string; className: string }> = {
  risk: { label: 'Ryzyko', className: 'bg-sun-100 text-sun-700 ring-1 ring-sun-300' },
  check: { label: 'Sprawdź', className: 'bg-sun-100 text-sun-700' },
  ok: { label: 'W porządku', className: 'bg-zus-50 text-zus-700' },
  info: { label: 'Dobrze wiedzieć', className: 'bg-navy-50 text-navy-500' },
}

interface Line {
  id: string
  level: Level
  icon: string
  title: string
  /** The engine's words, or the source's when the engine has no point about it. */
  text: string
  sources: SourceRef[]
  /** The engine's point: opens in "Dlaczego tak?". */
  note?: string
  zus?: boolean
}

/** The quotes the engine keeps with its parameters (params/2026.json), by block and name. */
type Quotes = Record<string, Record<string, { sources?: SourceRef[] } | undefined> | undefined>
const quoted = (q: Quotes | null, block: string, name: string) => q?.[block]?.[name]?.sources ?? []

/** The first quote, as a sentence. */
const said = (sources: SourceRef[]) => {
  const quote = sources[0]?.quote ?? ''
  return quote ? `„${quote.charAt(0).toUpperCase()}${quote.slice(1)}${/[.!?]$/.test(quote) ? '' : '…'}”` : ''
}

function lines(timeline: Timeline, scenario: Scenario | null, q: Quotes | null): Line[] {
  const note = (id: string) => timeline.notes.find((n) => n.id === id)
  const fromNote = (n: CaseNote, icon: string, extra: Partial<Line> = {}): Line => ({
    id: n.id,
    level: n.kind === 'risk' ? 'risk' : 'ok',
    icon,
    title: n.title,
    text: n.text,
    sources: n.sources,
    note: n.id,
    ...extra,
  })
  const work = (parent: 'mother' | 'father') =>
    scenario?.role === parent ? scenario.work : parent === 'mother' ? scenario?.mother_work : scenario?.father_work
  const own = (w: string | null | undefined) => w === 'contract' || w === 'business'
  const out: Line[] = []

  // H.3: sickness insurance on the day of the birth.
  const insurance = note('insurance')
  if (insurance) out.push(fromNote(insurance, ICONS.parasol, { zus: insurance.kind === 'risk' }))
  if (!timeline.child_born && !timeline.taken_in && work('mother') && work('mother') !== 'none') {
    const sources = quoted(q, 'benefit', 'work_ended_before_birth')
    if (sources.length)
      out.push({ id: 'work-ended', level: 'check', icon: ICONS.kalendarz, title: 'Koniec pracy przed porodem', text: said(sources), sources })
  }

  // Contribution debt (ustawa art. 2a): the engine's point when the debt is known.
  for (const parent of ['mother', 'father'] as const) {
    const debt = note(`debt-${parent}`)
    if (debt) out.push(fromNote(debt, ICONS.pieniadze, { zus: debt.kind === 'risk' }))
    else if (work(parent) === 'business') {
      const sources = quoted(q, 'contribution_debt', 'rule')
      if (sources.length)
        out.push({
          id: `debt-${parent}-unknown`,
          level: 'check',
          icon: ICONS.pieniadze,
          title: `Zaległe składki ${parent === 'mother' ? 'mamy' : 'taty'}`,
          text: said(sources.slice(1)) || said(sources),
          sources,
          zus: true,
        })
    }
  }

  // H.1: a contract or business "dla pozoru".
  const sham = note('risk-sham')
  if (sham) out.push(fromNote(sham, ICONS.zlecenie))
  else {
    const sources = quoted(q, 'pregnancy', 'risk_sham')
    if (sources.length)
      out.push({ id: 'sham', level: 'info', icon: ICONS.zlecenie, title: 'Umowa albo firma „dla pozoru”', text: said(sources.slice(1)), sources })
  }

  // H.2: a contribution base raised in pregnancy (those who declare their base).
  const raised = note('risk-base')
  if (raised) out.push(fromNote(raised, ICONS.skarbonka))
  else if (own(work('mother')) || own(work('father'))) {
    const sources = quoted(q, 'pregnancy', 'risk_base_raised')
    if (sources.length)
      out.push({ id: 'raise', level: 'info', icon: ICONS.skarbonka, title: 'Podwyższenie podstawy składek w ciąży', text: said(sources), sources })
  }
  return out
}

export function RiskRadar({
  timeline,
  scenario,
  onCheckZus,
  onWhy,
}: {
  timeline: Timeline
  scenario: Scenario | null
  onCheckZus: () => void
  /** Open "Dlaczego tak?" at the engine's point. */
  onWhy: (noteId: string) => void
}) {
  const [quotes, setQuotes] = useState<Quotes | null>(null)
  useEffect(() => {
    fetchAdminParams()
      .then((view) => setQuotes(view.base as unknown as Quotes))
      .catch(() => setQuotes(null))
  }, [])

  const list = lines(timeline, scenario, quotes)
  // The contribution debt row rests on the ustawa, not on the guide's pages.
  const debt = list.some((line) => line.id.startsWith('debt-'))
  // After a loss the plan speaks gently and only of what the mother is owed: no risk list.
  if (list.length === 0 || timeline.notes.some((n) => n.id === 'loss' || n.text.startsWith('Bardzo nam przykro'))) return null
  return (
    <motion.section variants={ITEM} className="mt-10 lg:mt-12" aria-labelledby="risk-radar">
      <h2 id="risk-radar" className="text-2xl leading-tight font-bold tracking-tight text-navy-900">
        Na co uważać
      </h2>
      <p className="mt-1 text-navy-500">
        Co może zabrać albo obniżyć zasiłek · Przewodnik ZUS, s. 9–10{debt && '; ustawa zasiłkowa, art. 2a'}
      </p>
      <ul className="mt-5 divide-y divide-line rounded-3xl border border-line">
        {list.map((line) => (
          <Row key={line.id} line={line} onCheckZus={onCheckZus} onWhy={onWhy} />
        ))}
      </ul>
    </motion.section>
  )
}

function Row({ line, onCheckZus, onWhy }: { line: Line; onCheckZus: () => void; onWhy: (id: string) => void }) {
  const [open, setOpen] = useState(false)
  const level = LEVEL[line.level]
  return (
    <li className="flex items-start gap-3 px-4 py-4 sm:gap-4 sm:px-5">
      <Illustration src={line.icon} size="event" className="bg-white" />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-bold', level.className)}>{level.label}</span>
          <span className="font-bold text-navy-900">{line.title}</span>
        </p>
        <p className="mt-1 line-clamp-3 text-sm leading-relaxed text-navy-500">{line.text}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm font-bold">
          {line.note ? (
            <button type="button" onClick={() => onWhy(line.note!)} className="flex items-center gap-0.5 text-zus-700 hover:text-zus-900">
              Dlaczego tak? <ChevronRight className="size-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              className="flex items-center gap-1 text-zus-700 hover:text-zus-900"
            >
              Źródło
              <ChevronDown className={cn('size-4 transition-transform duration-200', open && 'rotate-180')} />
            </button>
          )}
          {line.zus && (
            <button type="button" onClick={onCheckZus} className="text-navy-500 hover:text-navy-900">
              Sprawdź w danych z ZUS
            </button>
          )}
        </div>
        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
              transition={{ duration: 0.22, ease: EASE_OUT }}
              className="overflow-hidden"
            >
              <div className="space-y-2 pt-2 text-sm">
                {line.sources.map((source) => (
                  <figure key={source.quote}>
                    <blockquote className="text-navy-700">„{source.quote}”</blockquote>
                    <figcaption className="text-xs text-navy-400">{sourceLabel(source)}</figcaption>
                  </figure>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </li>
  )
}
