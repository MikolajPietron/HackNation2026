import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import blizniaki from '@/assets/onboarding/blizniaki.webp'
import dom from '@/assets/onboarding/dom.webp'
import dziecko from '@/assets/onboarding/dziecko.webp'
import etat from '@/assets/onboarding/etat.webp'
import firma from '@/assets/onboarding/firma.webp'
import inkubator from '@/assets/onboarding/inkubator.webp'
import lozeczko from '@/assets/onboarding/lozeczko.webp'
import mama from '@/assets/onboarding/mama.webp'
import noworodek from '@/assets/onboarding/noworodek.webp'
import odpoczynek from '@/assets/onboarding/odpoczynek.webp'
import parasol from '@/assets/onboarding/parasol.webp'
import przyjecie from '@/assets/onboarding/przyjecie.webp'
import serce from '@/assets/onboarding/serce.webp'
import tata from '@/assets/onboarding/tata.webp'
import zlecenie from '@/assets/onboarding/zlecenie.webp'
import { MObywatelLogin } from '@/components/mocks/MObywatelLogin'
import { MockModal, SimBadge } from '@/components/mocks/MockModal'
import { SampleFamilies } from '@/components/cases/SampleFamilies'
import { TextStates } from '@/components/ui/text-states'
import { addDaysIso, formatLongDate, todayIso } from '@/lib/dates'
import type { Persona } from '@/lib/mockData'
import { plural } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type {
  OnboardingAnswers,
  PayerSize,
  Role,
  SessionStart,
  TakenIn,
  Work,
  WorkFacts,
} from '@/types'
import { CALENDAR_CELL, CALENDAR_WIDTH, Calendar } from './Calendar'
import { ImageChoice, PrimaryButton, TextChoice } from './ChoiceCard'
import { ITEM, POP, STEP } from './motion'

/** "Nie wiem": an answer, unlike null (not answered yet). The chat asks it again later. */
type Unknown = 'unknown'

/** One parent's work as far as the onboarding learned it. */
interface WorkAnswers {
  /** The respondent always knows their own work; "unknown" only for the other parent. */
  work: Work | Unknown | null
  /** Contract or business: registered for the voluntary sickness insurance. */
  insured: boolean | Unknown | null
  /** Employment or contract: does the payer report more than 20 people? */
  payer: PayerSize | null
  /** Gross salary (employee) or the base of the sickness contribution, per month. */
  pay: number | Unknown | null
}

type SickLeave = 'now' | 'ended' | 'no' | Unknown

/**
 * What the parent told us, while the questions are being answered. Everything is saved in the
 * session (see toAnswers) and every fact is one question fewer in the chat: the first plan shows
 * whether the benefit is due, who pays it and how much, for both parents.
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
  /** The respondent's own work. */
  own: WorkAnswers
  /** The other parent's work, as the respondent knows it. */
  partner: WorkAnswers
  /** Born child: premature or in hospital after the birth. */
  hospital: boolean | null
  /** Born child: the mother was on maternity leave before the birth. */
  tookLeave: boolean | Unknown | null
  /** How many weeks before the birth; null with `tookLeave` = more than the cards offer. */
  leaveWeeks: number | null
  /** Child on the way: the mother's sick leave in this pregnancy. */
  sick: SickLeave | null
  sickStart: string
  sickEnd: string
  /** The test account of the simulated mObywatel login: the respondent's work and sick leave
   *  come from its ZUS data instead of questions. */
  zus: Persona | null
}

const ILLUSTRATIONS = [
  mama,
  tata,
  dziecko,
  lozeczko,
  blizniaki,
  etat,
  zlecenie,
  firma,
  dom,
  serce,
  inkubator,
  noworodek,
  odpoczynek,
  parasol,
]

const NO_WORK: WorkAnswers = { work: null, insured: null, payer: null, pay: null }

const EMPTY: Answers = {
  role: null,
  born: null,
  takenIn: null,
  children: null,
  date: '',
  childBirth: '',
  own: NO_WORK,
  partner: NO_WORK,
  hospital: null,
  tookLeave: null,
  leaveWeeks: null,
  sick: null,
  sickStart: '',
  sickEnd: '',
  zus: null,
}

type Who = 'own' | 'partner'

const WORK_STEPS = {
  own: { work: 'work', insurance: 'insurance', payer: 'payer', pay: 'pay' },
  partner: {
    work: 'partner-work',
    insurance: 'partner-insurance',
    payer: 'partner-payer',
    pay: 'partner-pay',
  },
} as const

type WorkStep = (typeof WORK_STEPS)[Who][keyof (typeof WORK_STEPS)[Who]]

type StepId =
  | 'intro'
  | 'role'
  | 'born'
  | 'kind'
  | 'children'
  | 'date'
  | 'child-birth'
  | 'hospital'
  | WorkStep
  | 'leave-before'
  | 'leave-weeks'
  | 'sick-leave'
  | 'sick-start'
  | 'sick-end'
  | 'zus-data'
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
/** A pregnancy is not longer than this, so sick leave in it cannot start earlier. */
const PREGNANCY_MAX_DAYS = 300
/** The monthly amount: the backend rejects less (a typo like 8 for 8000). */
const MIN_PAY = 100
const MAX_PAY = 1_000_000
const CALCULATING = ['Sprawdzamy ubezpieczenie…', 'Liczymy urlopy i zasiłki…', 'Układamy oś czasu…']

const PAID: (Work | Unknown | null)[] = ['employment', 'contract', 'business']
/** Contract or business: sickness insurance is voluntary. */
const voluntary = (work: WorkAnswers['work']) => work === 'contract' || work === 'business'
/** Employment or contract: somebody else pays the benefit if they report more than 20 people. */
const hasPayer = (work: WorkAnswers['work']) => work === 'employment' || work === 'contract'
/** Not known to be without sickness insurance (the chat's interview asks on the same terms). */
const mayBeInsured = (facts: WorkAnswers) =>
  facts.work !== 'none' && !(voluntary(facts.work) && facts.insured === false)
/** Known to be insured. */
const isInsured = (facts: WorkAnswers) =>
  facts.work === 'employment' || (voluntary(facts.work) && facts.insured === true)

const mothersWork = (a: Answers) => (a.role === 'father' ? a.partner : a.own)
const bornHere = (a: Answers) => a.born === true && a.takenIn === null
const expecting = (a: Answers) => a.born === false && a.takenIn === null

/** The order of the questions. The mother's own questions follow her work. */
function order(a: Answers): StepId[] {
  const work = (who: Who): StepId[] =>
    who === 'own'
      ? ['work', 'zus-data', 'insurance', 'payer', 'pay']
      : Object.values(WORK_STEPS.partner)
  const mother: StepId[] = ['leave-before', 'leave-weeks', 'sick-leave', 'sick-start', 'sick-end']
  const parents =
    a.role === 'father'
      ? [...work('own'), ...work('partner'), ...mother]
      : [...work('own'), ...mother, ...work('partner')]
  return [
    'intro',
    'role',
    'born',
    'kind',
    'children',
    'date',
    'child-birth',
    'hospital',
    ...parents,
    'calculating',
  ]
}

/** Questions the simulated ZUS data answers for the respondent. */
const FROM_ZUS: StepId[] = ['insurance', 'payer', 'pay', 'sick-leave', 'sick-start', 'sick-end']

/** Whether a question is asked: it concerns this family and nothing answered it yet. */
function applies(step: StepId, a: Answers): boolean {
  return relevant(step, a) && !(a.zus !== null && FROM_ZUS.includes(step))
}

/** Whether a question concerns this family. Mirrors the chat's interview, so whatever the
 *  onboarding learns, the chat does not ask again. */
function relevant(step: StepId, a: Answers): boolean {
  const who: Who = step.startsWith('partner-') ? 'partner' : 'own'
  const facts = a[who]
  switch (step) {
    case 'kind':
    case 'child-birth':
      return a.takenIn !== null
    case 'hospital':
      return bornHere(a)
    case 'insurance':
    case 'partner-insurance':
      return voluntary(facts.work)
    // Who pays and how much: the engine counts them for a birth, not yet for a child taken in.
    case 'payer':
    case 'partner-payer':
      return a.takenIn === null && hasPayer(facts.work)
    case 'pay':
    case 'partner-pay':
      return a.takenIn === null && PAID.includes(facts.work) && facts.insured !== false
    case 'leave-before':
      return bornHere(a) && mayBeInsured(mothersWork(a))
    case 'leave-weeks':
      return relevant('leave-before', a) && a.tookLeave === true
    case 'sick-leave':
      return expecting(a) && isInsured(mothersWork(a))
    case 'sick-start':
      return relevant('sick-leave', a) && (a.sick === 'now' || a.sick === 'ended')
    case 'sick-end':
      return relevant('sick-leave', a) && a.sick === 'ended'
    case 'zus-data':
      return a.zus !== null
    default:
      return true
  }
}

/** The next question for these answers. */
function after(step: StepId, a: Answers): StepId {
  const steps = order(a)
  const rest = steps.slice(steps.indexOf(step) + 1)
  return rest.find((next) => applies(next, a)) ?? 'calculating'
}

/** The finished answers, in the shape the backend stores. Answers to questions that no longer
 *  apply (an earlier answer changed) are left out. */
function toAnswers(a: Answers): OnboardingAnswers {
  const takenIn = a.takenIn
  const facts = (who: Who): WorkFacts => {
    const f = a[who]
    const steps = WORK_STEPS[who]
    return {
      work: f.work === 'unknown' ? null : f.work,
      insured: relevant(steps.insurance, a) && f.insured !== 'unknown' ? f.insured : null,
      payer_size: relevant(steps.payer, a) ? f.payer : null,
      pay: relevant(steps.pay, a) ? f.pay : null,
    }
  }
  const own = facts('own')
  const leave = relevant('leave-before', a) ? a.tookLeave : null
  const sick = relevant('sick-leave', a) && a.sick !== 'unknown' ? a.sick : null
  return {
    role: a.role ?? 'mother',
    child_born: takenIn ? true : (a.born ?? false),
    date: takenIn ? a.childBirth : a.date,
    children_count: a.children ?? 1,
    work: own.work ?? 'none',
    insured: own.insured,
    payer_size: own.payer_size,
    pay: own.pay,
    partner: facts('partner'),
    taken_in: takenIn ? { kind: takenIn, date: a.date } : null,
    hospital_care: relevant('hospital', a) ? a.hospital : null,
    leave_before_birth_weeks: leave === false ? 0 : leave === true ? a.leaveWeeks : null,
    sick_leave: sick === null ? null : sick !== 'no',
    sick_leave_start: sick === 'now' || sick === 'ended' ? a.sickStart : null,
    sick_leave_end: sick === 'ended' ? a.sickEnd : null,
    insured_since: a.zus?.facts.insuredSince ?? null,
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
  const [loginOpen, setLoginOpen] = useState(false)
  const [examplesOpen, setExamplesOpen] = useState(false)
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
  /** Straight to the next question that applies, for steps with their own button. */
  const next = (current: StepId, a: Answers = answers) => go(after(current, a))
  const backTo = (target?: StepId) => {
    window.clearTimeout(timer.current)
    setLeaving(false)
    setPath((p) => {
      const index = target ? p.lastIndexOf(target) : p.length - 2
      return index >= 0 ? p.slice(0, index + 1) : p
    })
  }
  /** Record an answer, let the selection land, then move on to the next question that applies. */
  const choose = (patch: Partial<Answers>) => {
    if (leaving) return
    const updated = { ...answers, ...patch }
    setAnswers(updated)
    setLeaving(true)
    timer.current = window.setTimeout(() => go(after(step, updated)), CHOICE_DELAY_MS)
  }
  /** A changed answer about one parent's work: what was said about the old work goes. */
  const chooseWork = (who: Who, patch: Partial<WorkAnswers>) => {
    const before = answers[who]
    const kept = patch.work === undefined || patch.work === before.work ? before : NO_WORK
    const facts = { ...kept, ...patch }
    // Answered by hand: the data from the simulated login no longer stands for it.
    choose(who === 'own' ? { own: facts, zus: null } : { partner: facts })
  }
  /** The simulated mObywatel login: the test account's ZUS data answers the questions about the
   *  respondent's work and sick leave. */
  const fromZus = (persona: Persona) => {
    const f = persona.facts
    setAnswers({
      ...answers,
      zus: persona,
      own: { work: f.work, insured: f.insured, payer: f.payer, pay: f.pay },
      sick: f.sickLeave ? 'ended' : 'no',
      sickStart: f.sickLeave?.start ?? '',
      sickEnd: f.sickLeave?.end ?? '',
    })
    setLoginOpen(false)
    go('zus-data')
  }
  /** Another role: what was said about "my" work was said by somebody else. */
  const pickRole = (role: Role) =>
    choose(
      answers.role === role
        ? { role }
        : {
            role,
            own: NO_WORK,
            partner: NO_WORK,
            tookLeave: null,
            leaveWeeks: null,
            sick: null,
            sickStart: '',
            sickEnd: '',
          },
    )
  const pick = (selected: boolean) => ({ selected, dimmed: leaving && !selected })
  const state = <K extends keyof Answers>(key: K, value: Answers[K]) => pick(answers[key] === value)

  // Who the questions are about: the respondent ("Ty") or the other parent, by name.
  const motherFills = answers.role !== 'father'
  const partnerName = motherFills ? 'tata' : 'mama'
  const several = (answers.children ?? 1) > 1

  let screen: ReactNode
  switch (step) {
    case 'intro':
      screen = <Intro onStart={() => go('role')} onSkip={onSkip} onExample={() => setExamplesOpen(true)} saved={saved} />
      break
    case 'role':
      screen = (
        <Question title="Kim jesteś?" subtitle="Dopasujemy do tego wyjaśnienia.">
          <Cards label="Kim jesteś?">
            <ImageChoice
              image={mama}
              label="Mamą"
              {...state('role', 'mother')}
              onSelect={() => pickRole('mother')}
            />
            <ImageChoice
              image={tata}
              label="Tatą"
              {...state('role', 'father')}
              onSelect={() => pickRole('father')}
            />
          </Cards>
        </Question>
      )
      break
    case 'born': {
      // The date limits differ, so a changed answer clears the date.
      const same = (born: boolean) => answers.born === born && answers.takenIn === null
      const pickBorn = (born: boolean) =>
        choose({ born, takenIn: null, date: same(born) ? answers.date : '' })
      screen = (
        <Question title="Czy dziecko jest już na świecie?">
          <Cards label="Czy dziecko jest już na świecie?" three>
            <ImageChoice
              image={lozeczko}
              label="Czekamy na nie"
              hint="Jesteśmy w ciąży"
              {...pick(same(false))}
              onSelect={() => pickBorn(false)}
            />
            <ImageChoice
              image={dziecko}
              label="Już jest z nami"
              hint="Dziecko się urodziło"
              {...pick(same(true))}
              onSelect={() => pickBorn(true)}
            />
            {/* Guide section D: a child taken in for upbringing. On phones the third card takes
                the whole row, with a smaller picture, so the step still fits the screen. */}
            <ImageChoice
              image={przyjecie}
              label="Przyjmujemy dziecko"
              hint="Adopcja albo rodzina zastępcza"
              selected={answers.takenIn !== null}
              dimmed={leaving && answers.takenIn === null}
              onSelect={() => !leaving && go('kind')}
              className="col-span-2 sm:col-span-1 [&_img]:max-h-[16vh] sm:[&_img]:max-h-[34vh]"
            />
          </Cards>
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
              onSelect={() => choose({ children: 1 })}
            />
            <ImageChoice
              image={blizniaki}
              label={answers.takenIn ? 'Dwoje' : 'Bliźnięta'}
              {...state('children', 2)}
              onSelect={() => choose({ children: 2 })}
            />
          </Cards>
          <MoreChildren
            value={answers.children}
            leaving={leaving}
            onSelect={(children) => choose({ children })}
          />
        </Question>
      )
      break
    case 'date': {
      const today = todayIso()
      screen = (
        <DateStep
          {...dateStep(
            answers.takenIn ? 'taken-in' : answers.born ? 'birth' : 'due',
            today,
            answers.takenIn === 'adoption',
            several,
            '',
          )}
          value={answers.date}
          onChange={(date) => setAnswers((a) => ({ ...a, date }))}
          onNext={() => next('date')}
        />
      )
      break
    }
    case 'child-birth':
      screen = (
        <DateStep
          {...dateStep('child-birth', todayIso(), false, several, answers.date)}
          value={answers.childBirth}
          onChange={(childBirth) => setAnswers((a) => ({ ...a, childBirth }))}
          onNext={() => next('child-birth')}
        />
      )
      break
    case 'hospital':
      screen = (
        <Question
          title={
            several
              ? 'Czy któreś z dzieci było po porodzie w szpitalu?'
              : 'Czy dziecko było po porodzie w szpitalu?'
          }
          subtitle={`Albo ${several ? 'dzieci urodziły się' : 'urodziło się'} przed ukończeniem 37. tygodnia ciąży. Szczegóły dopytamy w rozmowie.`}
        >
          <Cards label="Pobyt w szpitalu po porodzie">
            <ImageChoice
              image={inkubator}
              label="Tak"
              hint="wcześniak albo szpital"
              {...state('hospital', true)}
              onSelect={() => choose({ hospital: true })}
            />
            <ImageChoice
              image={noworodek}
              label="Nie"
              hint="w terminie, bez szpitala"
              {...state('hospital', false)}
              onSelect={() => choose({ hospital: false })}
            />
          </Cards>
        </Question>
      )
      break
    case 'work':
    case 'partner-work': {
      const who: Who = step === 'work' ? 'own' : 'partner'
      const own = who === 'own'
      const facts = answers[who]
      const card = (work: Work, image: string, label: string, hint?: string) => (
        <ImageChoice
          image={image}
          label={label}
          hint={hint}
          {...pick(facts.work === work)}
          onSelect={() => chooseWork(who, { work })}
        />
      )
      screen = (
        <Question
          title={own ? 'Jak pracujesz?' : `Jak pracuje ${partnerName}?`}
          subtitle={
            own
              ? 'Od tego zależy, czy masz prawo do zasiłku i kto go wypłaci.'
              : motherFills
                ? 'Od tego zależą urlopy taty i jego zasiłek.'
                : 'Od tego zależy, czy mama ma prawo do zasiłku macierzyńskiego.'
          }
        >
          <Cards label={own ? 'Jak pracujesz?' : `Jak pracuje ${partnerName}?`} wide>
            {card('employment', etat, 'Na etacie', 'umowa o pracę')}
            {card('contract', zlecenie, 'Na zleceniu', 'umowa zlecenia')}
            {card('business', firma, 'Własna firma', 'JDG')}
            {card('none', dom, own ? 'Nie pracuję' : 'Nie pracuje')}
          </Cards>
          {!own && (
            <UnknownLink
              selected={facts.work === 'unknown'}
              onSelect={() => !leaving && chooseWork(who, { work: 'unknown' })}
            />
          )}
          {/* The test accounts are mothers, so the shortcut is hers. */}
          {own && motherFills && (
            <motion.div variants={ITEM} className="mt-8 flex justify-center">
              <button
                type="button"
                onClick={() => !leaving && setLoginOpen(true)}
                className="flex h-11 items-center gap-2 rounded-full px-4 text-sm font-bold text-navy-500 transition-colors hover:bg-navy-50 hover:text-navy-900"
              >
                Pobierz dane z ZUS przez mObywatel
                <SimBadge>symulacja</SimBadge>
              </button>
            </motion.div>
          )}
        </Question>
      )
      break
    }
    case 'zus-data': {
      const persona = answers.zus
      const sick = persona?.ezla.map((z) => `${z.from} – ${z.to} (kod ${z.code})`).join(', ')
      screen = persona && (
        <Question title="Twoje dane z ZUS" subtitle="Nie musisz ich wpisywać. Sprawdź, czy się zgadzają.">
          <motion.div
            variants={ITEM}
            className="mx-auto w-full max-w-md rounded-4xl border border-line bg-white p-6 text-left shadow-card sm:p-7"
          >
            <div className="flex items-center gap-3">
              <img src={parasol} alt="" draggable={false} className="size-12 object-contain" />
              <p className="min-w-0 flex-1 text-lg font-bold text-navy-900">{persona.name}</p>
              <SimBadge>symulacja</SimBadge>
            </div>
            <dl className="mt-5 space-y-3">
              <Fact label="Praca" value={persona.work} />
              <Fact label="Ubezpieczenie chorobowe" value={persona.sickness} />
              <Fact label="Kto wypłaca zasiłek" value={persona.payer} />
              <Fact label="Podstawa składek" value={`${persona.contributionBase} miesięcznie`} />
              <Fact label="Zwolnienia e-ZLA" value={sick || 'brak'} />
              <Fact label="Zadłużenie składkowe" value={persona.debt} />
            </dl>
          </motion.div>
          <motion.div variants={ITEM} className="mt-8 flex justify-center">
            <PrimaryButton onClick={() => next('zus-data')}>
              Dalej <ArrowRight className="size-5" />
            </PrimaryButton>
          </motion.div>
        </Question>
      )
      break
    }
    case 'insurance':
    case 'partner-insurance': {
      const who: Who = step === 'insurance' ? 'own' : 'partner'
      const own = who === 'own'
      const facts = answers[who]
      // The person asked about: the mother when she fills in herself, or when the father does.
      const registered = own === motherFills ? 'zgłoszona' : 'zgłoszony'
      const options: { value: boolean | Unknown; label: string; hint?: string }[] = [
        {
          value: true,
          label: own ? `Tak, jestem ${registered}` : `Tak, jest ${registered}`,
          hint: own ? 'opłacam składkę chorobową' : 'opłaca składkę chorobową',
        },
        { value: false, label: own ? `Nie, nie jestem ${registered}` : `Nie, nie jest ${registered}` },
        { value: 'unknown', label: 'Nie wiem' },
      ]
      screen = (
        <Question
          title={own ? 'Czy opłacasz składkę chorobową?' : `Czy ${partnerName} opłaca składkę chorobową?`}
          subtitle={`Przy ${facts.work === 'contract' ? 'umowie zlecenia' : 'własnej firmie'} ubezpieczenie chorobowe jest dobrowolne. Od niego zależy prawo do zasiłku.`}
        >
          <Rows label="Ubezpieczenie chorobowe">
            {options.map((option) => (
              <TextChoice
                key={String(option.value)}
                label={option.label}
                hint={option.hint}
                {...pick(facts.insured === option.value)}
                onSelect={() => chooseWork(who, { insured: option.value })}
              />
            ))}
          </Rows>
        </Question>
      )
      break
    }
    case 'payer':
    case 'partner-payer': {
      const who: Who = step === 'payer' ? 'own' : 'partner'
      const own = who === 'own'
      const facts = answers[who]
      const employer = facts.work === 'employment'
      const payer = employer ? 'pracodawca' : 'zleceniodawca'
      const whose = motherFills ? 'taty' : 'mamy'
      const options: { value: PayerSize; label: string; hint?: string }[] = [
        { value: 'over-20', label: 'Więcej niż 20', hint: `zasiłek wypłaci ${payer}` },
        { value: 'up-to-20', label: '20 lub mniej', hint: 'zasiłek wypłaci ZUS' },
        { value: 'unknown', label: 'Nie wiem' },
      ]
      screen = (
        <Question
          title={
            own
              ? `Ile osób zgłasza do ubezpieczenia Twój ${payer}?`
              : `Ile osób zgłasza do ubezpieczenia ${payer} ${whose}?`
          }
          subtitle={`Chodzi o ubezpieczenie chorobowe. Od tego zależy, kto wypłaci zasiłek i gdzie ${own ? 'złożysz' : 'trafi'} wniosek.`}
        >
          <Rows label="Kto wypłaci zasiłek">
            {options.map((option) => (
              <TextChoice
                key={option.value}
                label={option.label}
                hint={option.hint}
                {...pick(facts.payer === option.value)}
                onSelect={() => chooseWork(who, { payer: option.value })}
              />
            ))}
          </Rows>
        </Question>
      )
      break
    }
    case 'pay':
    case 'partner-pay': {
      const who: Who = step === 'pay' ? 'own' : 'partner'
      const facts = answers[who]
      const record = (pay: number | Unknown) => {
        const changed = { ...facts, pay }
        const updated = who === 'own' ? { ...answers, own: changed } : { ...answers, partner: changed }
        setAnswers(updated)
        next(step, updated)
      }
      screen = (
        <PayStep
          key={step}
          {...payWording(facts.work, who === 'own', partnerName)}
          value={facts.pay}
          onSubmit={record}
          onUnknown={() => record('unknown')}
        />
      )
      break
    }
    case 'leave-before': {
      const own = motherFills
      screen = (
        <Question
          title={
            own
              ? 'Czy byłaś na urlopie macierzyńskim przed porodem?'
              : 'Czy mama była na urlopie macierzyńskim przed porodem?'
          }
          subtitle="Tygodnie sprzed porodu wliczają się do urlopu macierzyńskiego."
        >
          <Cards label="Urlop przed porodem">
            <ImageChoice
              image={odpoczynek}
              label="Tak"
              hint="urlop zaczął się przed porodem"
              {...state('tookLeave', true)}
              onSelect={() => choose({ tookLeave: true })}
            />
            <ImageChoice
              image={etat}
              label="Nie"
              hint={own ? 'pracowałam do porodu' : 'pracowała do porodu'}
              {...state('tookLeave', false)}
              onSelect={() => choose({ tookLeave: false, leaveWeeks: null })}
            />
          </Cards>
          {!own && (
            <UnknownLink
              selected={answers.tookLeave === 'unknown'}
              onSelect={() => choose({ tookLeave: 'unknown', leaveWeeks: null })}
            />
          )}
        </Question>
      )
      break
    }
    case 'leave-weeks':
      screen = (
        <Question
          title={
            motherFills
              ? 'Ile tygodni przed porodem zaczęłaś urlop?'
              : 'Ile tygodni przed porodem mama zaczęła urlop?'
          }
          subtitle="W pełnych tygodniach, licząc od dnia porodu."
        >
          <Pills
            label="Tygodnie przed porodem"
            options={[1, 2, 3, 4, 5, 6].map((weeks) => ({ value: weeks, label: String(weeks) }))}
            value={answers.leaveWeeks}
            leaving={leaving}
            onSelect={(leaveWeeks) => choose({ leaveWeeks })}
          />
          {/* A child born after the due date: more weeks than the cards. The chat asks. */}
          <motion.div variants={ITEM} className="mt-6 flex h-11 justify-center">
            <button
              type="button"
              onClick={() => choose({ leaveWeeks: null })}
              className="h-11 text-sm font-bold text-navy-500 transition-colors hover:text-navy-900"
            >
              Więcej niż 6
            </button>
          </motion.div>
        </Question>
      )
      break
    case 'sick-leave': {
      const own = motherFills
      const options: { value: SickLeave; label: string }[] = [
        { value: 'now', label: own ? 'Tak, jestem teraz' : 'Tak, jest teraz' },
        { value: 'ended', label: own ? 'Byłam, już się skończyło' : 'Była, już się skończyło' },
        { value: 'no', label: 'Nie' },
        ...(own ? [] : [{ value: 'unknown' as const, label: 'Nie wiem' }]),
      ]
      screen = (
        <Question
          title={
            own
              ? 'Czy w tej ciąży jesteś na zwolnieniu lekarskim?'
              : 'Czy mama jest w tej ciąży na zwolnieniu lekarskim?'
          }
          subtitle="Pokażemy na osi, kto płaci za zwolnienie i ile."
        >
          <Rows label="Zwolnienie lekarskie w ciąży">
            {options.map((option) => (
              <TextChoice
                key={option.value}
                label={option.label}
                {...state('sick', option.value)}
                onSelect={() => choose({ sick: option.value })}
              />
            ))}
          </Rows>
        </Question>
      )
      break
    }
    case 'sick-start': {
      const today = todayIso()
      const ongoing = answers.sick === 'now'
      screen = (
        <DateStep
          title={
            motherFills
              ? ongoing
                ? 'Od kiedy jesteś na zwolnieniu?'
                : 'Od kiedy byłaś na zwolnieniu?'
              : ongoing
                ? 'Od kiedy mama jest na zwolnieniu?'
                : 'Od kiedy mama była na zwolnieniu?'
          }
          subtitle="Pierwszy dzień zwolnienia lekarskiego."
          min={addDaysIso(answers.date || today, -PREGNANCY_MAX_DAYS)}
          max={today}
          value={answers.sickStart}
          onChange={(sickStart) =>
            setAnswers((a) => ({ ...a, sickStart, sickEnd: a.sickEnd < sickStart ? '' : a.sickEnd }))
          }
          onNext={() => next('sick-start')}
        />
      )
      break
    }
    case 'sick-end':
      screen = (
        <DateStep
          title="Do kiedy trwało zwolnienie?"
          subtitle="Ostatni dzień zwolnienia lekarskiego."
          min={answers.sickStart}
          max={todayIso()}
          value={answers.sickEnd}
          onChange={(sickEnd) => setAnswers((a) => ({ ...a, sickEnd }))}
          onNext={() => next('sick-end')}
        />
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

      <MObywatelLogin open={loginOpen} onClose={() => setLoginOpen(false)} onLogin={fromZus} />
      <MockModal open={examplesOpen} label="Przykładowe rodziny" onClose={() => setExamplesOpen(false)} className="max-w-4xl">
        <h2 className="pr-10 text-2xl leading-tight font-bold tracking-tight text-navy-900">Zobacz na przykładzie</h2>
        <p className="mt-1 text-navy-500">
          Wybierz rodzinę, a pokażemy jej cały plan. Swój policzysz potem, odpowiadając na pytania.
        </p>
        <SampleFamilies
          className="mt-5"
          onLoaded={(start) => {
            setExamplesOpen(false)
            onDone(start)
          }}
        />
      </MockModal>

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

/** The amount question in the words of the form of work: the benefit base is the gross salary of
 *  an employee, but the declared base of the sickness contribution on a contract or in a business
 *  (not the income). */
function payWording(work: WorkAnswers['work'], own: boolean, partnerName: string) {
  const whose = partnerName === 'tata' ? 'taty' : 'mamy'
  const average = 'Jeśli w ostatnich 12 miesiącach się zmieniała, podaj średnią.'
  switch (work) {
    case 'employment':
      return {
        title: own ? 'Ile zarabiasz brutto miesięcznie?' : `Ile ${partnerName} zarabia brutto miesięcznie?`,
        subtitle:
          'Z umowy o pracę. Jeśli w ostatnich 12 miesiącach się zmieniało, podaj średnią. Policzymy z tego zasiłek.',
      }
    case 'contract':
      return {
        title: own
          ? 'Jaka jest Twoja podstawa składki chorobowej?'
          : `Jaka jest podstawa składki chorobowej ${whose}?`,
        subtitle: `Miesięcznie, z umowy zlecenia. ${average}`,
      }
    default:
      return {
        title: own
          ? 'Jaką podstawę składki chorobowej deklarujesz?'
          : `Jaką podstawę składki chorobowej deklaruje ${partnerName}?`,
        subtitle: `Miesięcznie, w firmie: kwota, od której ${own ? 'płacisz' : 'płaci'} składki, a nie przychód. ${average}`,
      }
  }
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

function Cards({
  label,
  wide,
  three,
  children,
}: {
  label: string
  wide?: boolean
  /** Three cards side by side from `sm`; on phones two, and the third under them. */
  three?: boolean
  children: ReactNode
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        'mx-auto grid w-full grid-cols-2 gap-3 sm:gap-6',
        wide ? 'max-w-5xl lg:grid-cols-4' : three ? 'max-w-5xl sm:grid-cols-3' : 'max-w-3xl',
      )}
    >
      {children}
    </div>
  )
}

/** Answers without pictures, one under the other. */
function Rows({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="radiogroup" aria-label={label} className="mx-auto w-full max-w-md space-y-3">
      {children}
    </div>
  )
}

/** One line of the data from ZUS. */
function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-navy-500">{label}</dt>
      <dd className="font-bold text-navy-900">{value}</dd>
    </div>
  )
}

/** "Nie wiem" under picture cards: about the other parent, the respondent may not know. */
function UnknownLink({ selected, onSelect }: { selected: boolean; onSelect: () => void }) {
  return (
    <motion.div variants={ITEM} className="mt-8 flex h-11 justify-center">
      <button
        type="button"
        role="radio"
        aria-checked={selected}
        onClick={onSelect}
        className={cn(
          'h-11 rounded-full px-5 text-sm font-bold transition-colors',
          selected ? 'bg-zus-50 text-zus-900' : 'text-navy-500 hover:text-navy-900',
        )}
      >
        Nie wiem
      </button>
    </motion.div>
  )
}

function Intro({
  onStart,
  onSkip,
  onExample,
  saved,
}: {
  onStart: () => void
  onSkip: () => void
  /** Open a ready example family instead of answering (no AI). */
  onExample: () => void
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
        <button
          type="button"
          onClick={onExample}
          className="text-sm font-bold text-zus-700 underline-offset-4 transition-colors hover:text-zus-900 hover:underline"
        >
          Zobacz na przykładowej rodzinie
        </button>
      </motion.div>
    </div>
  )
}

/** A row of round number buttons. */
function Pills({
  label,
  options,
  value,
  leaving,
  onSelect,
}: {
  label: string
  options: { value: number; label: string }[]
  value: number | null
  leaving: boolean
  onSelect: (value: number) => void
}) {
  return (
    <motion.div
      variants={ITEM}
      role="radiogroup"
      aria-label={label}
      className="mx-auto flex max-w-md flex-wrap items-center justify-center gap-2 sm:gap-3"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          onClick={() => !leaving && onSelect(option.value)}
          className={cn(
            'size-14 rounded-full border text-lg font-bold transition-[border-color,background-color,opacity,transform] duration-200 active:scale-[0.96] sm:size-16',
            value === option.value
              ? 'border-zus-600 bg-zus-50 text-zus-900'
              : 'border-line text-navy-900 hover:border-navy-200',
            leaving && value !== option.value && 'opacity-40',
          )}
        >
          {option.label}
        </button>
      ))}
    </motion.div>
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

interface DateQuestion {
  title: string
  subtitle: string
  min: string
  max: string
}

function dateStep(
  kind: DateKind,
  today: string,
  adoption: boolean,
  several: boolean,
  takenInOn: string,
): DateQuestion {
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
  title,
  subtitle,
  min,
  max,
  value,
  onChange,
  onNext,
}: DateQuestion & {
  value: string
  onChange: (date: string) => void
  onNext: () => void
}) {
  const today = todayIso()
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
              <TextStates text={valid ? distance(value, today) : ' '} />
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

const money = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' })

/** "7 500", "7500,50", "7 500 zł" → 7500.5; null when it is not an amount. */
function parseAmount(text: string): number | null {
  const plain = text.replace(/\s|zł/gi, '').replace(',', '.')
  if (!/^\d+(\.\d{1,2})?$/.test(plain)) return null
  return Number(plain)
}

/** The monthly amount the benefit is computed from, or "Nie wiem" (then no amounts yet). */
function PayStep({
  title,
  subtitle,
  value,
  onSubmit,
  onUnknown,
}: {
  title: string
  subtitle: string
  value: number | Unknown | null
  onSubmit: (amount: number) => void
  onUnknown: () => void
}) {
  const [text, setText] = useState(typeof value === 'number' ? String(value).replace('.', ',') : '')
  const input = useRef<HTMLInputElement>(null)
  const amount = parseAmount(text)
  const valid = amount !== null && amount >= MIN_PAY && amount <= MAX_PAY
  // The field is the whole step: focus it without scrolling (the step slides in).
  useEffect(() => input.current?.focus({ preventScroll: true }), [])

  const note =
    text === ''
      ? ' '
      : valid
        ? `${money.format(amount)} miesięcznie`
        : 'Podaj kwotę miesięczną w złotych, np. 7500.'

  return (
    <Question title={title} subtitle={subtitle}>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (valid) onSubmit(amount)
        }}
        className="mx-auto w-full max-w-sm"
      >
        <motion.label
          variants={ITEM}
          className="flex h-20 items-center gap-3 rounded-3xl border border-line bg-white px-6 shadow-card transition-[border-color,box-shadow] duration-200 focus-within:border-zus-600 focus-within:shadow-[0_0_0_1px_var(--color-zus-600)]"
        >
          <span className="sr-only">{title}</span>
          <input
            ref={input}
            inputMode="decimal"
            autoComplete="off"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="np. 7 500"
            className="min-w-0 flex-1 bg-transparent text-3xl font-bold text-navy-900 outline-none placeholder:font-normal placeholder:text-navy-300"
          />
          <span className="text-2xl font-bold text-navy-400" aria-hidden>
            zł
          </span>
        </motion.label>
        <motion.p
          variants={ITEM}
          className={cn('mt-3 text-sm', text !== '' && !valid ? 'text-navy-900' : 'text-navy-500')}
          aria-live="polite"
        >
          {note}
        </motion.p>
        <motion.div variants={ITEM} className="mt-8 flex flex-col items-center gap-5">
          <PrimaryButton type="submit" disabled={!valid}>
            Dalej <ArrowRight className="size-5" />
          </PrimaryButton>
          <button
            type="button"
            onClick={onUnknown}
            className="text-sm font-bold text-navy-500 transition-colors hover:text-navy-900"
          >
            Nie wiem albo wolę nie podawać
          </button>
        </motion.div>
      </form>
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
