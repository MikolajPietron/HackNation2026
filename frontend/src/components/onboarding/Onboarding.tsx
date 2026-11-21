import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import blizniaki from '@/assets/onboarding/blizniaki.webp'
import dom from '@/assets/onboarding/dom.webp'
import dziecko from '@/assets/onboarding/dziecko.webp'
import etat from '@/assets/onboarding/etat.webp'
import firma from '@/assets/onboarding/firma.webp'
import lozeczko from '@/assets/onboarding/lozeczko.webp'
import mama from '@/assets/onboarding/mama.webp'
import serce from '@/assets/onboarding/serce.webp'
import tata from '@/assets/onboarding/tata.webp'
import zlecenie from '@/assets/onboarding/zlecenie.webp'
import { TextStates } from '@/components/ui/text-states'
import { addDaysIso, formatLongDate, todayIso } from '@/lib/dates'
import { plural } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { Earnings, OnboardingAnswers, Role, SessionStart, TakenIn, Work } from '@/types'
import { CALENDAR_CELL, CALENDAR_WIDTH, Calendar } from './Calendar'
import { ImageChoice, PrimaryButton, TextChoice } from './ChoiceCard'
import { ITEM, POP, STEP } from './motion'

/**
 * What the parent told us, while the questions are being answered. All of it is saved in the
 * session (see toAnswers): the date, birth and children feed the timeline; role, work and
 * earnings guide the assistant now and later phases (who pays, applications, amounts).
 */
interface Answers {
  role: Role | null
  born: boolean | null
  /** Guide section D: the child is taken in for upbringing (then `born` is true). */
  takenIn: TakenIn | null
  children: number | null
  /** ISO date: birth date when `born`, otherwise the due date; the day of taking in for `takenIn`. */
  date: string
  /** ISO date: the child's date of birth, asked only for `takenIn`. */
  childBirth: string
  work: Work | null
  earnings: Earnings | null
}

const ILLUSTRATIONS = [mama, tata, dziecko, lozeczko, blizniaki, etat, zlecenie, firma, dom, serce]

const EMPTY: Answers = {
  role: null,
  born: null,
  takenIn: null,
  children: null,
  date: '',
  childBirth: '',
  work: null,
  earnings: null,
}

type StepId =
  | 'intro'
  | 'role'
  | 'born'
  | 'kind'
  | 'children'
  | 'date'
  | 'child-birth'
  | 'work'
  | 'earnings'
  | 'calculating'

/** Pause after a tap so the choice visibly lands before the step leaves. */
const CHOICE_DELAY_MS = 320
/** The calculation is fast; its screen stays long enough to read instead of flashing. */
const MIN_CALCULATING_MS = 1400
const DUE_DATE_MAX_DAYS_AHEAD = 300
const BIRTH_DATE_MAX_DAYS_AGO = 6 * 366
/** A child taken in: the day of taking in may be years back, the child up to its teens. */
const TAKEN_IN_MAX_DAYS_AGO = 14 * 366
const CHILD_BIRTH_MAX_DAYS_AGO = 18 * 366
const CALCULATING = ['Sprawdzamy terminy…', 'Liczymy urlop macierzyński…', 'Układamy oś czasu…']

const EARNINGS: { value: Earnings; label: string }[] = [
  { value: 'under-5k', label: 'Do 5 000 zł' },
  { value: '5k-8k', label: '5 000 – 8 000 zł' },
  { value: '8k-12k', label: '8 000 – 12 000 zł' },
  { value: 'over-12k', label: 'Powyżej 12 000 zł' },
  { value: 'unknown', label: 'Nie wiem' },
]

/** The finished answers, in the shape the backend stores. */
function toAnswers(answers: Answers): OnboardingAnswers {
  const takenIn = answers.takenIn
  return {
    role: answers.role ?? 'mother',
    child_born: takenIn ? true : (answers.born ?? false),
    date: takenIn ? answers.childBirth : answers.date,
    children_count: answers.children ?? 1,
    work: answers.work ?? 'none',
    earnings: answers.work === 'none' ? null : answers.earnings,
    taken_in: takenIn ? { kind: takenIn, date: answers.date } : null,
  }
}

/** A conversation saved in this browser, which the start screen offers to resume. */
export interface SavedSession {
  summary: string
  onResume: () => void
}

interface Props {
  /** Saves the answers in the session and returns the first timeline. */
  submit: (answers: OnboardingAnswers, signal: AbortSignal) => Promise<SessionStart>
  onDone: (start: SessionStart) => void
  /** Go straight to the assistant. */
  onSkip: () => void
  /** Set when this browser already has a saved conversation. */
  saved: SavedSession | null
}

/** Full-screen questions, one per screen, then the first timeline. No progress bar on purpose. */
export function Onboarding({ submit, onDone, onSkip, saved }: Props) {
  const [path, setPath] = useState<StepId[]>(['intro'])
  const [answers, setAnswers] = useState<Answers>(EMPTY)
  const [leaving, setLeaving] = useState(false)
  const timer = useRef(0)
  const step = path[path.length - 1]

  useEffect(() => () => window.clearTimeout(timer.current), [])
  useEffect(() => {
    for (const src of ILLUSTRATIONS) new Image().src = src
  }, [])

  const go = (next: StepId) => {
    setLeaving(false)
    setPath((p) => [...p, next])
  }
  const backTo = (target?: StepId) => {
    window.clearTimeout(timer.current)
    setLeaving(false)
    setPath((p) => {
      const index = target ? p.lastIndexOf(target) : p.length - 2
      return index >= 0 ? p.slice(0, index + 1) : p
    })
  }
  /** Record an answer, let the selection land, then move on. */
  const choose = (patch: Partial<Answers>, next: StepId) => {
    if (leaving) return
    setAnswers((a) => ({ ...a, ...patch }))
    setLeaving(true)
    timer.current = window.setTimeout(() => go(next), CHOICE_DELAY_MS)
  }
  const state = <K extends keyof Answers>(key: K, value: Answers[K]) => ({
    selected: answers[key] === value,
    dimmed: leaving && answers[key] !== value,
  })

  let screen: ReactNode
  switch (step) {
    case 'intro':
      screen = <Intro onStart={() => go('role')} onSkip={onSkip} saved={saved} />
      break
    case 'role':
      screen = (
        <Question title="Kim jesteś?" subtitle="Dopasujemy do tego wyjaśnienia.">
          <Cards label="Kim jesteś?">
            <ImageChoice
              image={mama}
              label="Mamą"
              {...state('role', 'mother')}
              onSelect={() => choose({ role: 'mother' }, 'born')}
            />
            <ImageChoice
              image={tata}
              label="Tatą"
              {...state('role', 'father')}
              onSelect={() => choose({ role: 'father' }, 'born')}
            />
          </Cards>
        </Question>
      )
      break
    case 'born': {
      // The date limits differ, so a changed answer clears the date.
      const same = (born: boolean) => answers.born === born && answers.takenIn === null
      const pickBorn = (born: boolean) =>
        choose({ born, takenIn: null, date: same(born) ? answers.date : '' }, 'children')
      const card = (born: boolean) => ({
        selected: same(born),
        dimmed: leaving && !same(born),
      })
      screen = (
        <Question title="Czy dziecko jest już na świecie?">
          <Cards label="Czy dziecko jest już na świecie?">
            <ImageChoice
              image={lozeczko}
              label="Czekamy na nie"
              hint="Jesteśmy w ciąży"
              {...card(false)}
              onSelect={() => pickBorn(false)}
            />
            <ImageChoice
              image={dziecko}
              label="Już jest z nami"
              hint="Dziecko się urodziło"
              {...card(true)}
              onSelect={() => pickBorn(true)}
            />
          </Cards>
          {/* Guide section D: rarer, so a link instead of a third card. */}
          <motion.div variants={ITEM} className="mt-8 flex h-11 justify-center">
            <button
              type="button"
              onClick={() => !leaving && go('kind')}
              className="h-11 text-sm font-bold text-navy-500 transition-colors hover:text-navy-900"
            >
              Przyjmujemy dziecko na wychowanie (adopcja, rodzina zastępcza)
            </button>
          </motion.div>
        </Question>
      )
      break
    }
    case 'kind': {
      // The day of taking in and the child's birth mean something else for the other kind.
      const pickKind = (takenIn: TakenIn) =>
        choose(
          answers.takenIn === takenIn
            ? { born: true, takenIn }
            : { born: true, takenIn, date: '', childBirth: '' },
          'children',
        )
      screen = (
        <Question
          title="Jak przyjmujecie dziecko?"
          subtitle="Urlop jest wtedy na warunkach urlopu macierzyńskiego."
        >
          <Cards label="Jak przyjmujecie dziecko?">
            <ImageChoice
              image={serce}
              label="Adopcja"
              hint="wniosek do sądu o przysposobienie"
              {...state('takenIn', 'adoption')}
              onSelect={() => pickKind('adoption')}
            />
            <ImageChoice
              image={dom}
              label="Rodzina zastępcza"
              hint="niezawodowa"
              {...state('takenIn', 'foster')}
              onSelect={() => pickKind('foster')}
            />
          </Cards>
        </Question>
      )
      break
    }
    case 'children':
      screen = (
        <Question
          title={
            answers.takenIn
              ? 'Ile dzieci przyjmujecie?'
              : answers.born
                ? 'Ile dzieci się urodziło?'
                : 'Ile dzieci się urodzi?'
          }
          subtitle={
            answers.takenIn
              ? 'Przy jednoczesnym przyjęciu kilkorga dzieci urlop jest dłuższy.'
              : 'Przy ciąży mnogiej urlop macierzyński jest dłuższy.'
          }
        >
          <Cards label="Liczba dzieci">
            <ImageChoice
              image={dziecko}
              label="Jedno"
              {...state('children', 1)}
              onSelect={() => choose({ children: 1 }, 'date')}
            />
            <ImageChoice
              image={blizniaki}
              label={answers.takenIn ? 'Dwoje' : 'Bliźnięta'}
              {...state('children', 2)}
              onSelect={() => choose({ children: 2 }, 'date')}
            />
          </Cards>
          <MoreChildren
            value={answers.children}
            leaving={leaving}
            onSelect={(children) => choose({ children }, 'date')}
          />
        </Question>
      )
      break
    case 'date':
      screen = (
        <DateStep
          kind={answers.takenIn ? 'taken-in' : answers.born ? 'birth' : 'due'}
          adoption={answers.takenIn === 'adoption'}
          value={answers.date}
          onChange={(date) => setAnswers((a) => ({ ...a, date }))}
          onNext={() => go(answers.takenIn ? 'child-birth' : 'work')}
        />
      )
      break
    case 'child-birth':
      screen = (
        <DateStep
          kind="child-birth"
          several={(answers.children ?? 1) > 1}
          takenInOn={answers.date}
          value={answers.childBirth}
          onChange={(childBirth) => setAnswers((a) => ({ ...a, childBirth }))}
          onNext={() => go('work')}
        />
      )
      break
    case 'work': {
      const pickWork = (work: Work) => choose({ work }, work === 'none' ? 'calculating' : 'earnings')
      screen = (
        <Question
          title="Jak pracujesz?"
          subtitle="Od tego zależy, kto wypłaci zasiłek i gdzie złożysz wniosek."
        >
          <Cards label="Jak pracujesz?" wide>
            <ImageChoice
              image={etat}
              label="Na etacie"
              hint="umowa o pracę"
              {...state('work', 'employment')}
              onSelect={() => pickWork('employment')}
            />
            <ImageChoice
              image={zlecenie}
              label="Na zleceniu"
              hint="umowa zlecenia"
              {...state('work', 'contract')}
              onSelect={() => pickWork('contract')}
            />
            <ImageChoice
              image={firma}
              label="Własna firma"
              hint="JDG"
              {...state('work', 'business')}
              onSelect={() => pickWork('business')}
            />
            <ImageChoice
              image={dom}
              label="Nie pracuję"
              {...state('work', 'none')}
              onSelect={() => pickWork('none')}
            />
          </Cards>
        </Question>
      )
      break
    }
    case 'earnings':
      screen = (
        <Question title="Ile zarabiasz miesięcznie?" subtitle="Brutto, w przybliżeniu. Wystarczy przedział.">
          <div role="radiogroup" aria-label="Zarobki" className="mx-auto w-full max-w-md space-y-3">
            {EARNINGS.map((option) => (
              <TextChoice
                key={option.value}
                label={option.label}
                {...state('earnings', option.value)}
                onSelect={() => choose({ earnings: option.value }, 'calculating')}
              />
            ))}
          </div>
        </Question>
      )
      break
    case 'calculating':
      screen = (
        <Calculating
          answers={answers}
          submit={submit}
          onDone={onDone}
          onFix={() => backTo('date')}
        />
      )
      break
  }

  const canGoBack = step !== 'intro' && step !== 'calculating'

  return (
    <div className="relative flex h-dvh flex-col bg-white">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex h-16 items-center px-3 sm:px-6">
        <AnimatePresence>
          {canGoBack && (
            <motion.button
              type="button"
              onClick={() => backTo()}
              aria-label="Wstecz"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="pointer-events-auto grid size-11 place-items-center rounded-full text-navy-500 transition-colors hover:bg-navy-50 hover:text-navy-900 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
            >
              <ArrowLeft className="size-5" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence mode="wait">
        <motion.main
          key={step}
          variants={STEP}
          initial="enter"
          animate="center"
          exit="exit"
          className="min-h-0 flex-1 overflow-y-auto [scrollbar-gutter:stable]"
        >
          {screen}
        </motion.main>
      </AnimatePresence>
    </div>
  )
}

function Question({
  title,
  subtitle,
  compact = false,
  children,
}: {
  title: string
  subtitle?: string
  /** Less air around a tall answer (the calendar), so the step fits on one screen. */
  compact?: boolean
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        'flex min-h-full flex-col items-center justify-center px-5 text-center sm:px-8',
        compact ? 'pt-16 pb-6' : 'py-20',
      )}
    >
      <motion.h1
        variants={ITEM}
        className={cn(
          'max-w-3xl leading-[1.1] font-bold tracking-[-0.02em] text-balance text-navy-900',
          compact
            ? 'text-[30px] sm:text-4xl [@media(min-height:860px)]:sm:text-5xl'
            : 'text-[34px] sm:text-5xl',
        )}
      >
        {title}
      </motion.h1>
      {subtitle && (
        <motion.p
          variants={ITEM}
          className="mt-3 max-w-xl text-base text-pretty text-navy-500 sm:text-lg"
        >
          {subtitle}
        </motion.p>
      )}
      <div className={cn('w-full', compact ? 'mt-5 sm:mt-6' : 'mt-10 sm:mt-14')}>{children}</div>
    </div>
  )
}

function Cards({ label, wide, children }: { label: string; wide?: boolean; children: ReactNode }) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        'mx-auto grid w-full grid-cols-2 gap-3 sm:gap-6',
        wide ? 'max-w-5xl lg:grid-cols-4' : 'max-w-3xl',
      )}
    >
      {children}
    </div>
  )
}

function Intro({
  onStart,
  onSkip,
  saved,
}: {
  onStart: () => void
  onSkip: () => void
  saved: SavedSession | null
}) {
  return (
    <div className="mx-auto flex min-h-full w-full max-w-2xl flex-col items-center justify-center px-6 py-16 text-center">
      <div className="flex items-end justify-center" aria-hidden>
        <motion.img
          variants={POP}
          src={mama}
          alt=""
          className="-mr-3 w-32 select-none sm:-mr-4 sm:w-44"
        />
        <motion.img
          variants={POP}
          src={dziecko}
          alt=""
          className="relative w-20 select-none sm:w-28"
        />
        <motion.img
          variants={POP}
          src={tata}
          alt=""
          className="-ml-3 w-32 select-none sm:-ml-4 sm:w-44"
        />
      </div>
      <motion.h1
        variants={ITEM}
        className="mt-6 text-4xl leading-[1.05] font-bold tracking-tight text-balance text-navy-900 sm:text-6xl"
      >
        Policzmy, co Wam się należy
      </motion.h1>
      <motion.p variants={ITEM} className="mt-4 max-w-md text-lg text-pretty text-navy-500">
        Urlopy, zasiłki i terminy wniosków na jednej osi czasu. Kilka pytań, bez logowania.
      </motion.p>
      <motion.div variants={ITEM} className="mt-10 flex flex-col items-center gap-5">
        <PrimaryButton onClick={onStart}>
          {saved ? 'Zacznij nowy wywiad' : 'Zaczynamy'} <ArrowRight className="size-5" />
        </PrimaryButton>
        {saved ? (
          // The saved conversation stays until a new interview is finished.
          <button
            type="button"
            onClick={saved.onResume}
            className="rounded-2xl border border-line bg-white px-6 py-3 shadow-card transition-[border-color,transform] duration-150 hover:border-zus-300 active:scale-[0.98]"
          >
            <span className="block text-sm font-bold text-navy-900">
              Wróć do zapisanej osi czasu
            </span>
            <span className="block text-xs text-navy-500">{saved.summary}</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={onSkip}
            className="text-sm font-bold text-navy-500 transition-colors hover:text-navy-900"
          >
            Wolę porozmawiać z asystentem AI
          </button>
        )}
      </motion.div>
    </div>
  )
}

/** Triplets and more are rare: hidden behind a link instead of a third card. */
function MoreChildren({
  value,
  leaving,
  onSelect,
}: {
  value: number | null
  leaving: boolean
  onSelect: (children: number) => void
}) {
  const [open, setOpen] = useState((value ?? 0) > 2)
  return (
    <motion.div variants={ITEM} className="mt-8 flex h-11 justify-center">
      <AnimatePresence mode="wait" initial={false}>
        {open ? (
          <motion.div
            key="counts"
            role="radiogroup"
            aria-label="Więcej dzieci"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2"
          >
            {[3, 4, 5].map((count) => (
              <button
                key={count}
                type="button"
                role="radio"
                aria-checked={value === count}
                onClick={() => onSelect(count)}
                className={cn(
                  'h-11 rounded-full border px-5 font-bold transition-[border-color,background-color,opacity,transform] duration-200 active:scale-[0.96]',
                  value === count
                    ? 'border-zus-600 bg-zus-50 text-zus-900'
                    : 'border-line text-navy-900 hover:border-navy-200',
                  leaving && value !== count && 'opacity-40',
                )}
              >
                {count === 5 ? '5 lub więcej' : count}
              </button>
            ))}
          </motion.div>
        ) : (
          <motion.button
            key="link"
            type="button"
            onClick={() => setOpen(true)}
            exit={{ opacity: 0 }}
            className="h-11 text-sm font-bold text-navy-500 transition-colors hover:text-navy-900"
          >
            Trojaczki lub więcej?
          </motion.button>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

/** "za 17 tygodni" before the birth (pregnancy counts in weeks), "3 miesiące temu" after it. */
function distance(date: string, today: string): string {
  const days = Math.round((Date.parse(date) - Date.parse(today)) / 86_400_000)
  if (days === 0) return 'dziś'
  const n = Math.abs(days)
  const weeks = Math.floor(n / 7)
  const months = Math.floor(n / 30.44)
  const years = Math.floor(n / 365.25)
  const amount =
    n < 7
      ? `${n} ${plural(n, 'dzień', 'dni', 'dni')}`
      : days > 0 || n < 84
        ? `${weeks} ${plural(weeks, 'tydzień', 'tygodnie', 'tygodni')}`
        : years < 2
          ? `${months} ${plural(months, 'miesiąc', 'miesiące', 'miesięcy')}`
          : `${years} ${plural(years, 'rok', 'lata', 'lat')}`
  return days > 0 ? `za ${amount}` : `${amount} temu`
}

/** Which date the step asks for: the due date, the date of birth, or for a child taken in the
 *  day of taking in and the child's own date of birth. */
type DateKind = 'due' | 'birth' | 'taken-in' | 'child-birth'

function dateStep(kind: DateKind, today: string, adoption: boolean, several: boolean, takenInOn: string) {
  switch (kind) {
    case 'due':
      return {
        title: 'Kiedy jest termin porodu?',
        subtitle: 'Przewidywana data porodu z karty ciąży.',
        min: today,
        max: addDaysIso(today, DUE_DATE_MAX_DAYS_AHEAD),
      }
    case 'birth':
      return {
        title: 'Kiedy urodziło się dziecko?',
        subtitle: 'Data z aktu urodzenia.',
        min: addDaysIso(today, -BIRTH_DATE_MAX_DAYS_AGO),
        max: today,
      }
    case 'taken-in':
      return {
        title: 'Kiedy dziecko do Was trafiło?',
        subtitle: adoption
          ? 'Dzień przyjęcia dziecka. Jeśli wniosek o przysposobienie złożyliście w sądzie później, wybierz dzień wniosku.'
          : 'Dzień przyjęcia dziecka do rodziny zastępczej.',
        min: addDaysIso(today, -TAKEN_IN_MAX_DAYS_AGO),
        max: addDaysIso(today, DUE_DATE_MAX_DAYS_AHEAD),
      }
    case 'child-birth':
      return {
        title: several ? 'Kiedy urodziło się najmłodsze dziecko?' : 'Kiedy urodziło się dziecko?',
        subtitle: 'Od wieku dziecka zależy, jak długo trwa urlop.',
        min: addDaysIso(today, -CHILD_BIRTH_MAX_DAYS_AGO),
        // Born before it was taken in, and not in the future.
        max: takenInOn && takenInOn < today ? takenInOn : today,
      }
  }
}

function DateStep({
  kind,
  adoption = false,
  several = false,
  takenInOn = '',
  value,
  onChange,
  onNext,
}: {
  kind: DateKind
  adoption?: boolean
  several?: boolean
  takenInOn?: string
  value: string
  onChange: (date: string) => void
  onNext: () => void
}) {
  const today = todayIso()
  const { title, subtitle, min, max } = dateStep(kind, today, adoption, several, takenInOn)
  // ISO dates compare correctly as strings.
  const valid = value !== '' && value >= min && value <= max

  return (
    <Question title={title} subtitle={subtitle} compact>
      {/* The row under the calendar takes exactly its width: the date on the left edge, the
          button on the right edge, so the two line up and the button never moves. */}
      <div className={cn('mx-auto w-full', CALENDAR_CELL)} style={{ maxWidth: CALENDAR_WIDTH }}>
        <motion.div variants={ITEM}>
          <Calendar value={value} min={min} max={max} today={today} label={title} onChange={onChange} />
        </motion.div>
        <motion.div variants={ITEM} className="mt-4 flex items-center justify-between gap-3 pl-2">
          <p className="min-w-0 text-left leading-tight" aria-live="polite">
            <span className={cn('block text-lg', valid ? 'font-bold text-navy-900' : 'text-navy-400')}>
              <TextStates text={valid ? formatLongDate(value) : 'Wybierz dzień'} />
            </span>
            <span className="mt-0.5 block text-sm text-navy-500">
              <TextStates text={valid ? distance(value, today) : '\u00a0'} />
            </span>
          </p>
          <PrimaryButton disabled={!valid} onClick={onNext} className="shrink-0">
            Dalej <ArrowRight className="size-5" />
          </PrimaryButton>
        </motion.div>
      </div>
    </Question>
  )
}

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

function Calculating({
  answers,
  submit,
  onDone,
  onFix,
}: {
  answers: Answers
  submit: Props['submit']
  onDone: Props['onDone']
  onFix: () => void
}) {
  const [phase, setPhase] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const callbacks = useRef({ submit, onDone })
  useEffect(() => {
    callbacks.current = { submit, onDone }
  })

  useEffect(() => {
    const controller = new AbortController()
    const finished = toAnswers(answers)
    Promise.all([callbacks.current.submit(finished, controller.signal), wait(MIN_CALCULATING_MS)])
      .then(([start]) => {
        if (!controller.signal.aborted) callbacks.current.onDone(start)
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setError(reason instanceof Error ? reason.message : 'Nie udało się policzyć osi czasu.')
      })
    return () => controller.abort()
  }, [answers, attempt])

  useEffect(() => {
    const id = window.setInterval(
      () => setPhase((p) => Math.min(p + 1, CALCULATING.length - 1)),
      MIN_CALCULATING_MS / CALCULATING.length,
    )
    return () => window.clearInterval(id)
  }, [attempt])

  const retry = () => {
    setError(null)
    setPhase(0)
    setAttempt((a) => a + 1)
  }

  return (
    <div className="mx-auto flex min-h-full max-w-xl flex-col items-center justify-center px-6 py-16 text-center">
      <div className="flex items-end" aria-hidden>
        {[mama, dziecko, tata].map((src, index) => (
          <motion.div key={src} variants={POP}>
            <motion.img
              src={src}
              alt=""
              animate={error ? { y: 0 } : { y: [0, -8, 0] }}
              transition={{ duration: 1.1, repeat: error ? 0 : Infinity, delay: index * 0.14, ease: 'easeInOut' }}
              className={cn(
                'select-none',
                index === 1 ? 'w-16 sm:w-20' : 'w-24 sm:w-28',
              )}
            />
          </motion.div>
        ))}
      </div>
      <motion.p variants={ITEM} className="mt-8 text-2xl font-bold text-navy-900" aria-live="polite">
        <TextStates text={error ? 'Nie udało się policzyć' : CALCULATING[phase]} />
      </motion.p>
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3 flex flex-col items-center gap-6"
          >
            <p className="text-pretty text-navy-500">{error}</p>
            <div className="flex flex-col items-center gap-4">
              <PrimaryButton onClick={retry}>Spróbuj ponownie</PrimaryButton>
              <button
                type="button"
                onClick={onFix}
                className="text-sm font-bold text-navy-500 transition-colors hover:text-navy-900"
              >
                Zmień datę
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
