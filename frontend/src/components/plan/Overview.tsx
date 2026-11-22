// The top of the plan: the situation in one sentence, then the answers to the questions parents
// come with, each in a word or a number: are we entitled, how much leave do we have together,
// what now. The why (the case explanation with its sources) opens on a click, so nothing here
// is a wall of text. What stands in the way of an entitlement (a risk) is always shown in full,
// and so is what changes the plan because of the mother's or the child's situation.
// After a loss (a stillbirth, a child's or the mother's death) there are no tiles and no ticks:
// the engine's words of sympathy and what the family is entitled to, in full and calmly
// (CLAUDE.md, phase 3).
import { motion } from 'motion/react'
import { Check, ChevronRight, RotateCcw, TriangleAlert } from 'lucide-react'
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
import { entitlement, headline, leaveBudget, length, nextSteps, periodName } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { CaseNote, Segment, Timeline } from '@/types'

const BAR: Record<'mother' | 'father', Record<'leave' | 'option', string>> = {
  mother: { leave: 'bg-zus-600', option: 'bg-zus-200' },
  father: { leave: 'bg-navy-700', option: 'bg-navy-200' },
}

export function Overview({
  timeline,
  changed,
  wide,
  decisionPending,
  onWhy,
  onSelect,
  onStartOver,
  onMoney,
  onAsk,
}: {
  timeline: Timeline
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
}) {
  const { title, text } = headline(timeline)
  const right = entitlement(timeline.notes)
  const budget = leaveBudget(timeline)
  const steps = nextSteps(timeline)
  const step = steps.now[0] ?? steps.soon[0]
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
                <h1 className="mt-1 text-[26px] leading-tight font-bold tracking-tight text-navy-900 lg:text-[32px]">
                  {situation.title}
                </h1>
                <p className="mt-2 max-w-3xl text-[17px] leading-relaxed text-pretty text-navy-700">
                  {situation.text}
                </p>
              </>
            )}
          </div>
          {wide && <StartOver onClick={onStartOver} />}
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
    step && !decisionPending ? 'step' : null,
  ].filter(Boolean)
  // The tiles sit in a row when the plan column is wide enough, else two by two.
  const columns = tiles.length >= 4 ? '@[52rem]:grid-cols-4' : tiles.length === 3 ? '@[44rem]:grid-cols-3' : ''
  const moneySegment = money ? timeline.segments.find((s) => s.id === money.now.segment_id) : undefined

  return (
    <>
      <motion.header variants={ITEM} className="flex items-start gap-6">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-zus-700">Twoja sytuacja</p>
          <h1 className="mt-1 text-[26px] leading-tight font-bold tracking-tight text-balance text-navy-900 lg:text-[34px]">
            <TextStates text={title} />
          </h1>
          <p className="mt-2 max-w-4xl text-[17px] leading-relaxed text-pretty text-navy-500">
            {text && (
              <>
                <Emphasis text={text} className="text-navy-900" />{' '}
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
        {wide && <StartOver onClick={onStartOver} />}
      </motion.header>

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
              <span className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-navy-900">
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
              onClick={money ? onMoney : () => onAsk('Chcę podać moje miesięczne zarobki brutto')}
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

          {step && !decisionPending && (
            <Tile
              question={steps.now.length > 0 ? 'Co teraz?' : 'Co dalej?'}
              onClick={() => onSelect(step.id)}
              pulse={changedIds.has(step.id) ? changed.version : null}
            >
              <span className="flex items-start gap-2">
                <Illustration src={step.icon} size="hint" />
                <span className="min-w-0 text-lg leading-snug font-bold text-navy-900">
                  {step.decide ? `Wybierzcie: ${step.title.toLowerCase()}` : step.title}
                </span>
              </span>
              <span className="mt-1.5 block text-sm leading-snug text-navy-500">{step.detail}</span>
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
      className="mt-6 flex h-10 shrink-0 items-center gap-2 rounded-full px-4 text-sm font-bold text-navy-500 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.97]"
    >
      <RotateCcw className="size-4" /> Od nowa
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
