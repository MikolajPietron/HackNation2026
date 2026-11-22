// Example families (FUNKCJE F19: "Załaduj sprawę z gotowych danych; działa zawsze"): ready
// scenarios that open the plan at once, without AI and without the ZUS scans. Synthetic facts,
// no person behind them; each shows one thing the brief asks about. Dates are set from today so
// the example always stays current. The engine computes everything; this only states the facts.
import { addDaysIso } from './dates'
import { ICONS } from './icons'
import type { Scenario } from '../types'

export interface Sample {
  id: string
  title: string
  /** What the example shows, in a few words. */
  shows: string
  icon: string
  /** The facts for today's date. */
  facts: (today: string) => Partial<Scenario>
  /** Shown gently (a loss). */
  gentle?: boolean
}

/** Both parents employed: the mother's employer pays, the father's small one does not. */
const EMPLOYED: Partial<Scenario> = {
  role: 'mother',
  work: 'employment',
  mother_payer_size: 'over-20',
  father_work: 'employment',
  father_payer_size: 'up-to-20',
}

/** A child born `days` ago, at term, not in hospital, without leave before the birth. */
const born = (today: string, days: number): Partial<Scenario> => ({
  child_born: true,
  birth_date: addDaysIso(today, -days),
  children_count: 1,
  leave_before_birth_weeks: 0,
  hospital_care: false,
})

const yearsAgo = (today: string, years: number) => `${Number(today.slice(0, 4)) - years}${today.slice(4)}`

export const SAMPLES: Sample[] = [
  {
    id: 'first-child',
    title: 'Pierwsze dziecko w drodze',
    shows: 'Oboje na etacie: urlopy, kwoty, wnioski i terminy',
    icon: ICONS.wozek,
    facts: (today) => ({
      ...EMPLOYED,
      mother_pay: 7500,
      father_pay: 8200,
      child_born: false,
      due_date: addDaysIso(today, 95),
      children_count: 1,
      leave_before_birth_weeks: 2,
      has_medical_certificate: true,
      sick_leave: false,
    }),
  },
  {
    id: 'twins-premature',
    title: 'Bliźnięta, wcześniaki w szpitalu',
    shows: 'Dłuższy urlop i urlop uzupełniający za pobyt w szpitalu',
    icon: ICONS.blizniaki,
    facts: (today) => ({
      ...EMPLOYED,
      mother_pay: 6800,
      father_pay: 7400,
      child_born: true,
      birth_date: addDaysIso(today, -18),
      children_count: 2,
      leave_before_birth_weeks: 0,
      hospital_care: true,
      birth_week: '28-37',
      birth_weight_up_to_1000g: false,
      hospital_stays: [{ start: addDaysIso(today, -18), end: addDaysIso(today, 6) }],
    }),
  },
  {
    id: 'contract-no-insurance',
    title: 'Zlecenie bez chorobowego',
    shows: 'Kiedy zasiłek nie przysługuje i co zamiast',
    icon: ICONS.zlecenie,
    facts: (today) => ({
      role: 'mother',
      work: 'contract',
      mother_insured: false,
      father_work: 'employment',
      father_payer_size: 'up-to-20',
      father_pay: 7000,
      child_born: false,
      due_date: addDaysIso(today, 60),
      children_count: 1,
    }),
  },
  {
    id: 'business-debt',
    title: 'Własna firma z zaległymi składkami',
    shows: 'Zadłużenie składkowe a prawo do zasiłku',
    icon: ICONS.pieniadze,
    facts: (today) => ({
      role: 'mother',
      work: 'business',
      mother_insured: true,
      mother_contribution_debt: 1840,
      mother_pay: 5200,
      father_work: 'employment',
      father_payer_size: 'over-20',
      father_pay: 7600,
      ...born(today, 10),
    }),
  },
  {
    id: 'job-loss',
    title: 'Likwidacja pracodawcy w ciąży',
    shows: 'Zasiłek w wysokości zasiłku macierzyńskiego do porodu',
    icon: ICONS.karton,
    facts: (today) => ({
      ...EMPLOYED,
      mother_pay: 6500,
      father_pay: 7000,
      child_born: false,
      due_date: addDaysIso(today, 70),
      children_count: 1,
      leave_before_birth_weeks: 0,
      sick_leave: false,
      job_loss: { ended_on: addDaysIso(today, -5), reason: 'liquidation', court_confirmed: null },
    }),
  },
  {
    id: 'adoption',
    title: 'Adopcja dwulatka',
    shows: 'Urlop na warunkach urlopu macierzyńskiego i rodzicielski',
    icon: ICONS.przyjecie,
    facts: (today) => ({
      ...EMPLOYED,
      mother_pay: 7000,
      father_pay: 7800,
      taken_in: 'adoption',
      taken_in_on: addDaysIso(today, -3),
      child_born: true,
      birth_date: yearsAgo(today, 2),
      children_count: 1,
    }),
  },
  {
    id: 'father-takeover',
    title: 'Tata przejmuje urlop',
    shows: 'Po 14 tygodniach mama wraca do pracy, tata zostaje w domu',
    icon: ICONS.tataZDzieckiem,
    facts: (today) => ({ ...EMPLOYED, mother_pay: 9000, father_pay: 8000, ...born(today, 30), father_takes_over: true }),
  },
  {
    id: 'part-time',
    title: 'Urlop i praca na pół etatu',
    shows: 'Łączenie urlopu rodzicielskiego z pracą wydłuża urlop',
    icon: ICONS.etat,
    facts: (today) => ({
      ...EMPLOYED,
      mother_pay: 7000,
      father_pay: 7800,
      ...born(today, 40),
      parental_parts: [
        { parent: 'mother', weeks: 32, start: null, with_previous: false, work_fraction: '1/2', work_weeks: null },
        { parent: 'father', weeks: 9, start: null, with_previous: false, work_fraction: null, work_weeks: null },
      ],
    }),
  },
  {
    id: 'stillbirth',
    title: 'Martwe urodzenie',
    shows: 'Co przysługuje mamie; spokojny tryb bez kafelków',
    icon: ICONS.serce,
    gentle: true,
    facts: (today) => ({ ...EMPLOYED, mother_pay: 6000, ...born(today, 12), losses: [{ stillborn: true, died_on: null }] }),
  },
]
