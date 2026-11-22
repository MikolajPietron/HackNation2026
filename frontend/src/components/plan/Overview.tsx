// The top of the plan: the situation in one sentence, then the answers to the questions parents
// come with, each in a word or a number: are we entitled, how much leave do we have together,
// what now. The why (the case explanation with its sources) opens on a click, so nothing here
// is a wall of text. What stands in the way of an entitlement (a risk) is always shown in full,
// and so is what changes the plan because of the mother's or the child's situation.
// After a loss (a stillbirth, a child's or the mother's death) there are no tiles and no ticks:
// the engine's words of sympathy and what the family is entitled to, in full and calmly
// (CLAUDE.md, phase 3).
import { motion } from 'motion/react'
import { Check, ChevronRight, Lock, RotateCcw, Share2, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { ITEM } from '@/components/onboarding/motion'
import { Pulse } from '@/components/timeline/Pulse'
import { SupportList } from '@/components/support/SupportList'
import { Emphasis } from '@/components/ui/emphasis'
import { Illustration } from '@/components/ui/illustration'
import { TextStates } from '@/components/ui/text-states'
import type { ChangeSet } from '@/hooks/useAssistant'
import { SPRING_LAYOUT, SPRING_PRESS } from '@/lib/ease'
import { formatPlnShort, formatRate, headlinePayment } from '@/lib/money'
import { COUNTDOWN_DAYS, daysLeftLabel, entitlement, headline, leaveBudget, length, nextSteps, periodName, workOf } from '@/lib/plan'
import type { Step } from '@/lib/plan'
import { dayNumber, formatDistance, formatShortDate } from '@/lib/dates'
import { documentIcon, markerIcon } from '@/lib/icons'
import { cn } from '@/lib/utils'
import type { CaseNote, Scenario, Segment, Timeline } from '@/types'

const BAR: Record<'mother' | 'father', Record<'leave' | 'option', string>> = {
  mother: { leave: 'bg-zus-600', option: 'bg-zus-200' },
  father: { leave: 'bg-navy-700', option: 'bg-navy-200' },
}

export function Overview({
  timeline,
  scenario,
  changed,
  wide,
  decisionPending,
  onWhy,
  onSelect,
  onStartOver,
  onMoney,
  onAsk,
  onFill,
  onShare,
}: {
  timeline: Timeline
  /** How the parents work: the words for leave (a contract or a firm has the benefit, no leave). */
  scenario: Scenario | null
  changed: ChangeSet
  wide: boolean
  /** The interview has a question open: the decision card is "what now", no tile for it. */
  decisionPending: boolean
  onWhy: (noteId?: string) => void
  onSelect: (id: string) => void
  onStartOver: () => void
  /** Open "Dlaczego tyle?". */
  onMoney: () => void
  /** Say something to the assistant (e.g. give the pay). */
  onAsk: (prompt: string) => void
  /** Open a request to fill in (a document with a form). */
  onFill: (documentId: string) => void
  /** "Udostępnij plan": a read-only link for the partner. */
  onShare?: () => void
}) {
  const { title, text } = headline(timeline, scenario)
  const right = entitlement(timeline.notes)
  const budget = leaveBudget(timeline)
  const steps = nextSteps(timeline)
  const step = steps.now[0] ?? steps.soon[0]
  const task = todayTask(timeline, step)
  const risks = timeline.notes.filter((n) => n.kind === 'risk')
  const featured = timeline.notes.filter((n) => FEATURED.has(n.id))
  const changedIds = new Set(changed.ids)
  const situation = timeline.notes.find((n) => n.kind === 'situation')

  if (isLoss(timeline.notes)) {
    return (
      <>
        <motion.header variants={ITEM} className="flex items-start gap-6">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold text-navy-500">Twoja sytuacja</p>
            {situation && (
              <>
                <h1 data-read-aloud className="mt-1 text-[26px] leading-tight font-bold tracking-tight text-navy-900 lg:text-[32px]">
                  {situation.title}
                </h1>
                <p data-read-aloud className="mt-2 max-w-3xl text-[17px] leading-relaxed text-pretty text-navy-700">
                  {situation.text}
                </p>
              </>
            )}
          </div>
          {wide && (
            <div className="mt-6 flex shrink-0 items-center gap-1">
              {onShare && <ShareButton onClick={onShare} />}
              <StartOver onClick={onStartOver} />
            </div>
          )}
        </motion.header>
        {featured.map((note) => (
          <Featured key={note.id} note={note} changed={changed} onWhy={onWhy} />
        ))}
        {risks.map((risk) => (
          <Risk key={risk.id} note={risk} changed={changed} onWhy={onWhy} />
        ))}
        <motion.section variants={ITEM} className="mt-6 rounded-3xl bg-navy-50/50 px-5 py-5">
          <h2 className="font-bold text-navy-900">Gdzie szukać wsparcia</h2>
          <SupportList topics={['loss', 'crisis']} className="mt-3" />
        </motion.section>
      </>
    )
  }

  const money = headlinePayment(timeline)
  // Amounts need the pay: without it the tile asks for it (after a loss there are no tiles).
  const askPay = !money && budget.totalDays > 0
  const tiles = [
    right ? 'right' : null,
    budget.totalDays > 0 ? 'budget' : null,
    money || askPay ? 'money' : null,
  ].filter(Boolean)
  // The tiles sit in a row when the plan column is wide enough, else two by two.
  const columns = tiles.length >= 4 ? '@[52rem]:grid-cols-4' : tiles.length === 3 ? '@[44rem]:grid-cols-3' : ''
  const moneySegment = money ? timeline.segments.find((s) => s.id === money.now.segment_id) : undefined
  // On a contract or with one's own firm the amount is the contribution base, not pay (ustawa
  // zasiłkowa art. 3 pkt 4).
  const ownWork = scenario?.role ? workOf(scenario, scenario.role) : null
  const payPrompt =
    ownWork === 'contract' || ownWork === 'business'
      ? 'Chcę podać podstawę składki chorobowej'
      : 'Chcę podać moje miesięczne zarobki brutto'

  return (
    <>
      <motion.header variants={ITEM} className="flex items-start gap-6">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-zus-700">Twoja sytuacja</p>
          <h1 data-read-aloud className="mt-1 text-[26px] leading-tight font-bold tracking-tight text-balance text-navy-900 lg:text-[34px]">
            <TextStates text={title} />
          </h1>
          <p className="mt-2 max-w-4xl text-[17px] leading-relaxed text-pretty text-navy-500">
            {text && (
              <>
                <span data-read-aloud>
                  <Emphasis text={text} className="text-navy-900" />
                </span>{' '}
              </>
            )}
            <button
              type="button"
              onClick={() => onWhy()}
              className="inline-flex items-center gap-0.5 font-bold whitespace-nowrap text-zus-700 underline-offset-4 hover:underline"
            >
              Dlaczego tak? <ChevronRight className="size-4" />
            </button>
          </p>
        </div>
        {wide && (
          <div className="mt-6 flex shrink-0 items-center gap-1">
            {onShare && <ShareButton onClick={onShare} />}
            <StartOver onClick={onStartOver} />
          </div>
        )}
      </motion.header>

      {task && (!decisionPending || task.tone !== 'calm') && (
        <TodayStrip task={task} pulse={changedIds.has(task.id) ? changed.version : null} onSelect={onSelect} onFill={onFill} />
      )}

      {tiles.length > 0 && (
        <motion.div variants={ITEM} className="@container mt-5">
          <div className={cn('grid grid-cols-2 gap-2 @lg:gap-3 [&>*:last-child:nth-child(odd)]:col-span-2', columns, tiles.length >= 3 && '@[44rem]:[&>*:last-child:nth-child(odd)]:col-span-1')}>
          {right && (
            <Tile
              question="Czy nam się należy?"
              onClick={() => onWhy(right.id)}
              pulse={changed.notes.includes(right.id) ? changed.version : null}
            >
              <span className="flex items-center gap-2">
                <span
                  className={cn(
                    'grid size-8 shrink-0 place-items-center rounded-full',
                    right.kind === 'risk' ? 'bg-sun-400 text-navy-900' : 'bg-zus-600 text-white',
                  )}
                >
                  {right.kind === 'risk' ? <TriangleAlert className="size-4" /> : <Check className="size-4" strokeWidth={3} />}
                </span>
                <span className="text-2xl font-bold text-navy-900">
                  <TextStates text={right.kind === 'risk' ? 'Do sprawdzenia' : 'Tak'} />
                </span>
              </span>
              <span className="mt-2 block text-sm leading-snug text-navy-500">{right.title}</span>
            </Tile>
          )}

          {budget.totalDays > 0 && (
            <Tile
              question="Ile wolnego razem?"
              onClick={() => onWhy('computed')}
              pulse={[...budget.mother, ...budget.father].some((s) => changedIds.has(s.id)) ? changed.version : null}

            >
              {/* The number never breaks; on a narrow tile the words go under it. */}
              <span className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-2xl font-bold whitespace-nowrap text-navy-900">
                  <TextStates text={length(budget.totalDays)} />
                </span>
                <span className="text-sm text-navy-500">urlopu razem</span>
              </span>
              <Budget mother={budget.mother} father={budget.father} />
            </Tile>
          )}

          {(money || askPay) && (
            <Tile
              question="Ile dostaniecie?"
              onClick={money ? onMoney : () => onAsk(payPrompt)}
              pulse={money && changedIds.has(money.now.id) ? changed.version : null}
            >
              {money ? (
                <>
                  <span className="flex items-baseline gap-1.5">
                    <span className="text-2xl font-bold text-navy-900 tabular-nums">
                      <TextStates text={formatPlnShort(money.now.monthly)} />
                    </span>
                    <span className="text-sm text-navy-500">/ mies.</span>
                  </span>
                  <span className="mt-1 block text-sm leading-snug text-navy-500">
                    {money.now.lane === 'father' ? 'Tata' : 'Mama'}
                    {moneySegment ? `: ${periodName(moneySegment).toLowerCase()}` : ''} · {formatRate(money.now.rate)}
                  </span>
                  {money.then && (
                    <span className="block text-sm leading-snug text-navy-500">
                      potem <b className="text-navy-900 tabular-nums">{formatPlnShort(money.then.monthly)}</b> / mies.
                    </span>
                  )}
                  <span className="mt-1 block text-xs text-navy-400">brutto, przed podatkiem</span>
                </>
              ) : (
                <>
                  <span className="text-lg leading-snug font-bold text-navy-900">Podajcie zarobki</span>
                  <span className="mt-1 block text-sm leading-snug text-navy-500">
                    Policzymy zasiłek na każdy okres, krok po kroku.
                  </span>
                </>
              )}
            </Tile>
          )}

          </div>
        </motion.div>
      )}

      {featured.map((note) => (
        <Featured key={note.id} note={note} changed={changed} onWhy={onWhy} />
      ))}
      {risks.map((risk) => (
        <Risk key={risk.id} note={risk} changed={changed} onWhy={onWhy} />
      ))}
    </>
  )
}

/** Points that change the plan because of the mother's or the child's situation. */
const FEATURED = new Set(['loss', 'mother-event'])

/** A stillbirth, a child's death, or the mother's: the engine begins with words of sympathy. */
const isLoss = (notes: CaseNote[]) =>
  notes.some((n) => n.id === 'loss' || n.text.startsWith('Bardzo nam przykro'))

function StartOver({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-10 shrink-0 items-center gap-2 rounded-full px-4 text-sm font-bold text-navy-500 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.97]"
    >
      <RotateCcw className="size-4" /> Od nowa
    </button>
  )
}

function ShareButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-10 shrink-0 items-center gap-2 rounded-full px-4 text-sm font-bold text-navy-500 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.97]"
    >
      <Share2 className="size-4" /> Udostępnij
    </button>
  )
}

/** A point shown in full, calmly: a white card, no icon, the source one tap away. */
function Featured({
  note,
  changed,
  onWhy,
}: {
  note: CaseNote
  changed: ChangeSet
  onWhy: (noteId?: string) => void
}) {
  return (
    <motion.section variants={ITEM} className="relative mt-4 rounded-3xl border border-line px-5 py-4">
      {changed.notes.includes(note.id) && <Pulse key={changed.version} className="rounded-3xl" />}
      <p className="font-bold text-navy-900">{note.title}</p>
      <p className="mt-1 max-w-4xl leading-relaxed text-navy-700">
        <Emphasis text={note.text} className="text-navy-900" />
      </p>
      <button
        type="button"
        onClick={() => onWhy(note.id)}
        className="mt-1.5 text-sm font-bold text-zus-700 underline-offset-4 hover:underline"
      >
        Źródło i szczegóły
      </button>
    </motion.section>
  )
}

/** What stands in the way of an entitlement: amber, in full, never cut short. */
function Risk({
  note,
  changed,
  onWhy,
}: {
  note: CaseNote
  changed: ChangeSet
  onWhy: (noteId?: string) => void
}) {
  return (
    <motion.section variants={ITEM} className="relative mt-3 flex gap-3 rounded-3xl bg-sun-100 px-5 py-4 text-sun-700">
      {changed.notes.includes(note.id) && <Pulse key={changed.version} className="rounded-3xl" />}
      <TriangleAlert className="mt-0.5 size-5 shrink-0" />
      <div className="min-w-0">
        <p className="font-bold text-navy-900">{note.title}</p>
        <p className="mt-0.5 leading-relaxed text-navy-700">{note.text}</p>
        <button
          type="button"
          onClick={() => onWhy(note.id)}
          className="mt-1 text-sm font-bold text-sun-700 underline-offset-4 hover:underline"
        >
          Źródło i szczegóły
        </button>
      </div>
    </motion.section>
  )
}

function Tile({
  question,
  onClick,
  pulse,
  className,
  children,
}: {
  question: string
  onClick: () => void
  /** The change version when the last recalculation touched this answer. */
  pulse: number | null
  className?: string
  children: ReactNode
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileTap={{ scale: 0.98, transition: SPRING_PRESS }}
      className={cn(
        'group relative flex flex-col items-stretch rounded-3xl border border-line bg-white p-3.5 text-left @lg:p-5',
        'transition-[border-color,box-shadow] duration-200 hover:border-navy-200 hover:shadow-[0_12px_30px_-20px_rgb(26_36_56/0.35)]',
        'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        className,
      )}
    >
      {pulse !== null && <Pulse key={pulse} className="rounded-3xl" />}
      <span className="mb-2 flex items-center justify-between gap-1 text-[13px] leading-tight font-bold text-navy-500 @lg:text-sm">
        {question}
        <ChevronRight className="size-4 text-navy-300 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-navy-500" />
      </span>
      {children}
    </motion.button>
  )
}

/** The family's leave as one bar: the mother's then the father's, solid when set, light when
 *  still to decide. It grows and shrinks on a spring when the plan is recalculated. */
function Budget({ mother, father }: { mother: Segment[]; father: Segment[] }) {
  const parts = [...mother, ...father]
  const sum = (list: Segment[]) => list.reduce((total, s) => total + s.days, 0)
  return (
    <span className="mt-3 block">
      <span className="flex h-3 gap-0.5 overflow-hidden rounded-full">
        {parts.map((s) => (
          <motion.span
            key={s.id}
            title={`${periodName(s)} · ${length(s.days)}${s.tone === 'option' ? ' · do wyboru' : ''}`}
            className={cn('h-full min-w-1', BAR[s.lane === 'father' ? 'father' : 'mother'][s.tone === 'leave' ? 'leave' : 'option'])}
            initial={false}
            animate={{ flexGrow: s.days }}
            style={{ flexBasis: 0 }}
            transition={SPRING_LAYOUT}
          />
        ))}
      </span>
      <span className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {mother.length > 0 && (
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full bg-zus-600" />
            <span className="text-navy-500">Mama</span>
            <span className="font-bold text-navy-900">{length(sum(mother))}</span>
          </span>
        )}
        {father.length > 0 && (
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full bg-navy-700" />
            <span className="text-navy-500">Tata</span>
            <span className="font-bold text-navy-900">{length(sum(father))}</span>
          </span>
        )}
        {parts.some((s) => s.tone === 'option') && (
          <span className="hidden items-center gap-1.5 text-navy-500 @lg:flex">
            <span className="size-2.5 rounded-full bg-zus-200" />
            jaśniej: do wyboru
          </span>
        )}
      </span>
    </span>
  )
}

// ---------------------------------------------------------------------------------------------
// "Na dziś" (FUNKCJE F15): the plan starts with one thing to do and its deadline.

interface Today {
  id: string
  icon: string
  title: string
  detail: string
  /** overdue = the deadline has passed; soon = a deadline or a point of no return within weeks. */
  tone: 'overdue' | 'soon' | 'calm'
  /** A request to fill in. */
  fill: boolean
  noReturn: boolean
}

/** Picks the one thing: a missed deadline first, then the nearest deadline of a request or point
 *  of no return within the next weeks, then the first step ahead. Dates are the engine's. */
function todayTask(timeline: Timeline, step: Step | undefined): Today | null {
  const today = dayNumber(timeline.today)
  // A leave still to choose can start later, so its passed deadline is not missed: only the
  // requests for fixed days (supplementary leave, a takeover) can be overdue.
  const optional = (d: (typeof timeline.documents)[number]) =>
    timeline.segments.find((s) => s.id === d.segment_id)?.tone === 'option'
  const requests = timeline.documents
    .filter((d) => !d.done && d.deadline && !(optional(d) && dayNumber(d.deadline) < today))
    .sort((a, b) => a.deadline!.localeCompare(b.deadline!))
  const overdue = requests.find((d) => dayNumber(d.deadline!) < today)
  if (overdue)
    return {
      id: overdue.id,
      icon: documentIcon(overdue),
      title: `Złóż: ${overdue.title.charAt(0).toLowerCase()}${overdue.title.slice(1)}`,
      detail: `termin minął ${formatShortDate(overdue.deadline!)}`,
      tone: 'overdue',
      fill: overdue.form !== null,
      noReturn: false,
    }
  const near = [
    ...requests
      .filter((d) => dayNumber(d.deadline!) - today <= COUNTDOWN_DAYS)
      .map((d) => ({
        day: dayNumber(d.deadline!),
        task: {
          id: d.id,
          icon: documentIcon(d),
          title: `Złóż: ${d.title.charAt(0).toLowerCase()}${d.title.slice(1)}`,
          detail: `najpóźniej ${formatShortDate(d.deadline!)} · ${formatDistance(timeline.today, d.deadline!)}`,
          tone: 'soon' as const,
          fill: d.form !== null,
          noReturn: false,
        },
      })),
    ...timeline.markers
      .filter((m) => m.irreversible && m.irreversible.days_left >= 0 && m.irreversible.days_left <= COUNTDOWN_DAYS)
      .map((m) => ({
        day: dayNumber(m.date),
        task: {
          id: m.id,
          icon: markerIcon(m),
          title: m.title,
          detail: `${daysLeftLabel(m.irreversible!.days_left)} · ${formatShortDate(m.date)}`,
          tone: 'soon' as const,
          fill: false,
          noReturn: true,
        },
      })),
  ].sort((a, b) => a.day - b.day)
  if (near.length) return near[0].task
  if (!step) return null
  return { id: step.id, icon: step.icon, title: step.decide ? `Wybierzcie: ${step.title.toLowerCase()}` : step.title, detail: step.detail, tone: 'calm', fill: false, noReturn: false }
}

function TodayStrip({
  task,
  pulse,
  onSelect,
  onFill,
}: {
  task: Today
  pulse: number | null
  onSelect: (id: string) => void
  onFill: (id: string) => void
}) {
  const open = () => (task.fill ? onFill(task.id) : onSelect(task.id))
  const urgent = task.tone !== 'calm'
  const body = (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <Illustration src={task.icon} size="event" className="bg-white" />
      <div className="min-w-0">
        <p className="text-xs font-black tracking-wider text-navy-500 uppercase">Na dziś</p>
        <p className="leading-snug font-bold text-navy-900">{task.title}</p>
        <p
          className={cn(
            'flex flex-wrap items-center gap-1.5 text-sm',
            task.tone === 'overdue' ? 'font-bold text-alert-600' : urgent ? 'font-bold text-sun-700' : 'text-navy-500',
          )}
        >
          {task.noReturn && <Lock className="size-3.5" strokeWidth={2.5} />}
          {task.detail}
        </p>
      </div>
    </div>
  )
  // Nothing pressing: the strip is a quiet card that opens the step.
  if (!urgent)
    return (
      <motion.button
        variants={ITEM}
        type="button"
        onClick={open}
        aria-label={`Na dziś: ${task.title}`}
        whileTap={{ scale: 0.99, transition: SPRING_PRESS }}
        className="group relative mt-5 flex w-full items-center gap-3 rounded-3xl border border-line bg-white p-3 pr-4 text-left transition-colors hover:border-navy-200 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none sm:pl-4"
      >
        {pulse !== null && <Pulse key={pulse} className="rounded-3xl" />}
        {body}
        <ChevronRight className="size-5 shrink-0 text-navy-300 transition-transform group-hover:translate-x-0.5 group-hover:text-navy-500" />
      </motion.button>
    )
  return (
    <motion.section
      variants={ITEM}
      aria-label="Na dziś"
      className={cn(
        'relative mt-5 flex flex-col gap-3 rounded-3xl border p-3 sm:flex-row sm:items-center sm:gap-4 sm:pr-3 sm:pl-4',
        task.tone === 'overdue' ? 'border-alert-600/30 bg-alert-50/60' : 'border-sun-300 bg-sun-100/50',
      )}
    >
      {pulse !== null && <Pulse key={pulse} className="rounded-3xl" />}
      {body}
      <motion.button
        type="button"
        onClick={open}
        whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
        className="flex h-11 shrink-0 items-center justify-center gap-1 rounded-full bg-zus-600 px-5 text-sm font-bold text-white transition-colors hover:bg-zus-700 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2 focus-visible:outline-none"
      >
        {task.fill ? 'Wypełnij wniosek' : 'Zobacz'} <ChevronRight className="size-4" />
      </motion.button>
    </motion.section>
  )
}
