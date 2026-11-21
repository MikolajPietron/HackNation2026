import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import dziecko from '@/assets/onboarding/dziecko.webp'
import mama from '@/assets/onboarding/mama.webp'
import tata from '@/assets/onboarding/tata.webp'
import { TextStates } from '@/components/ui/text-states'
import { addDaysIso, formatLongDate, todayIso } from '@/lib/dates'
import { cn } from '@/lib/utils'
import type { Timeline } from '@/types'
import { Calendar } from './Calendar'
import { PrimaryButton } from './ChoiceCard'
import { ITEM, POP, STEP } from './motion'

// Phase 1 (guide section A.1): the onboarding asks only for the expected due date. The rest of
// the interview is in the chat. More steps (who is asking, children, work, earnings) come back
// with the phases that use them; their earlier version is in git history (commit 4092d06).

const ILLUSTRATIONS = [mama, tata, dziecko]

type StepId = 'intro' | 'date' | 'calculating'

/** The calculation is fast; its screen stays long enough to read instead of flashing. */
const MIN_CALCULATING_MS = 1400
const DUE_DATE_MAX_DAYS_AHEAD = 300
const CALCULATING = ['Sprawdzamy termin…', 'Liczymy urlop przed porodem…', 'Układamy oś czasu…']

interface Props {
  /** Stores the due date as the first answer of the interview and returns the timeline. */
  calculate: (dueDate: string, signal: AbortSignal) => Promise<Timeline>
  onDone: (timeline: Timeline) => void
  /** Go straight to the assistant. */
  onSkip: () => void
}

/** Full-screen start: one question, then the first timeline. No progress bar on purpose. */
export function Onboarding({ calculate, onDone, onSkip }: Props) {
  const [path, setPath] = useState<StepId[]>(['intro'])
  const [date, setDate] = useState('')
  const step = path[path.length - 1]

  useEffect(() => {
    for (const src of ILLUSTRATIONS) new Image().src = src
  }, [])

  const go = (next: StepId) => setPath((p) => [...p, next])
  const backTo = (target?: StepId) =>
    setPath((p) => {
      const index = target ? p.lastIndexOf(target) : p.length - 2
      return index >= 0 ? p.slice(0, index + 1) : p
    })

  let screen: ReactNode
  switch (step) {
    case 'intro':
      screen = <Intro onStart={() => go('date')} onSkip={onSkip} />
      break
    case 'date':
      screen = <DateStep value={date} onChange={setDate} onNext={() => go('calculating')} />
      break
    case 'calculating':
      screen = (
        <Calculating
          date={date}
          calculate={calculate}
          onDone={onDone}
          onFix={() => backTo('date')}
        />
      )
      break
  }

  const canGoBack = step === 'date'

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
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-5 py-20 text-center sm:px-8">
      <motion.h1
        variants={ITEM}
        className="max-w-3xl text-[34px] leading-[1.1] font-bold tracking-[-0.02em] text-balance text-navy-900 sm:text-5xl"
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
      <div className="mt-10 w-full sm:mt-14">{children}</div>
    </div>
  )
}

function Intro({ onStart, onSkip }: { onStart: () => void; onSkip: () => void }) {
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
        Przygotujmy się do porodu
      </motion.h1>
      <motion.p variants={ITEM} className="mt-4 max-w-md text-lg text-pretty text-navy-500">
        Od kiedy mama może zacząć urlop macierzyński i co warto przygotować. Jedno pytanie, bez logowania.
      </motion.p>
      <motion.div variants={ITEM} className="mt-10 flex flex-col items-center gap-5">
        <PrimaryButton onClick={onStart}>
          Zaczynamy <ArrowRight className="size-5" />
        </PrimaryButton>
        <button
          type="button"
          onClick={onSkip}
          className="text-sm font-bold text-navy-500 transition-colors hover:text-navy-900"
        >
          Wolę porozmawiać z asystentem AI
        </button>
      </motion.div>
    </div>
  )
}

function plural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one
  const last = n % 10
  const lastTwo = n % 100
  return last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? few : many
}

/** "za 17 tygodni" before the birth (pregnancy counts in weeks), "3 miesiące temu" after it. */
function distance(date: string, today: string): string {
  const days = Math.round((Date.parse(date) - Date.parse(today)) / 86_400_000)
  if (days === 0) return 'dziś'
  const n = Math.abs(days)
  const weeks = Math.floor(n / 7)
  const months = Math.floor(n / 30.44)
  const amount =
    n < 7
      ? `${n} ${plural(n, 'dzień', 'dni', 'dni')}`
      : days > 0 || n < 84
        ? `${weeks} ${plural(weeks, 'tydzień', 'tygodnie', 'tygodni')}`
        : `${months} ${plural(months, 'miesiąc', 'miesiące', 'miesięcy')}`
  return days > 0 ? `za ${amount}` : `${amount} temu`
}

function DateStep({
  value,
  onChange,
  onNext,
}: {
  value: string
  onChange: (date: string) => void
  onNext: () => void
}) {
  const today = todayIso()
  const max = addDaysIso(today, DUE_DATE_MAX_DAYS_AHEAD)
  // ISO dates compare correctly as strings.
  const valid = value !== '' && value >= today && value <= max
  const title = 'Kiedy jest termin porodu?'

  return (
    <Question title={title} subtitle="Przewidywana data porodu z karty ciąży.">
      <motion.div variants={ITEM}>
        <Calendar value={value} min={today} max={max} today={today} label={title} onChange={onChange} />
      </motion.div>
      <motion.div variants={ITEM} className="mt-6 flex flex-col items-center gap-5">
        <p className="h-7 text-lg" aria-live="polite">
          <TextStates
            text={valid ? `${formatLongDate(value)} · ${distance(value, today)}` : 'Wybierz dzień'}
            className={valid ? 'font-bold text-navy-900' : 'text-navy-400'}
          />
        </p>
        <PrimaryButton disabled={!valid} onClick={onNext}>
          Dalej <ArrowRight className="size-5" />
        </PrimaryButton>
      </motion.div>
    </Question>
  )
}

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

function Calculating({
  date,
  calculate,
  onDone,
  onFix,
}: {
  date: string
  calculate: Props['calculate']
  onDone: Props['onDone']
  onFix: () => void
}) {
  const [phase, setPhase] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const callbacks = useRef({ calculate, onDone })
  useEffect(() => {
    callbacks.current = { calculate, onDone }
  })

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([callbacks.current.calculate(date, controller.signal), wait(MIN_CALCULATING_MS)])
      .then(([timeline]) => {
        if (!controller.signal.aborted) callbacks.current.onDone(timeline)
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setError(reason instanceof Error ? reason.message : 'Nie udało się policzyć osi czasu.')
      })
    return () => controller.abort()
  }, [date, attempt])

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
