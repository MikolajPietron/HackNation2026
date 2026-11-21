// Example data for the simulated integrations (FUNKCJE F19, F30–F33). Synthetic: no data from
// the ZUS case files (CLAUDE.md: only case ids and topics may appear in the app).

export interface Persona {
  id: string
  name: string
  initials: string
  /** One line on the test account chooser. */
  about: string
  work: string
  payer: string
  sickness: string
  contributionBase: string
  debt: string
  ezla: { from: string; to: string; code: string; reason: string }[]
}

export const PERSONAS: Persona[] = [
  {
    id: 'anna',
    name: 'Anna Nowak',
    initials: 'AN',
    about: 'Umowa o pracę · w ciąży',
    work: 'Umowa o pracę (pełny etat)',
    payer: 'Przykładowa Spółka sp. z o.o. — ponad 20 osób, zasiłek wypłaca pracodawca',
    sickness: 'Obowiązkowe, od 1 marca 2023',
    contributionBase: '6 480,00 zł',
    debt: '0,00 zł',
    ezla: [{ from: '2 wrz 2026', to: '15 wrz 2026', code: 'B', reason: 'Niezdolność w okresie ciąży' }],
  },
  {
    id: 'kasia',
    name: 'Katarzyna Wiśniewska',
    initials: 'KW',
    about: 'Własna firma (JDG) · w ciąży',
    work: 'Pozarolnicza działalność gospodarcza',
    payer: 'Sama za siebie — zasiłek wypłaca ZUS',
    sickness: 'Dobrowolne, od 1 czerwca 2025',
    contributionBase: '5 400,00 zł',
    debt: '312,45 zł',
    ezla: [],
  },
  {
    id: 'marta',
    name: 'Marta Zielińska',
    initials: 'MZ',
    about: 'Umowa zlecenia · dziecko w drodze',
    work: 'Umowa zlecenia',
    payer: 'Przykładowe Biuro s.c. — do 20 osób, zasiłek wypłaca ZUS',
    sickness: 'Dobrowolne, od 1 lutego 2026',
    contributionBase: '4 200,00 zł',
    debt: '0,00 zł',
    ezla: [{ from: '10 paź 2026', to: '23 paź 2026', code: 'B', reason: 'Niezdolność w okresie ciąży' }],
  },
]

/** Plans from the goal (F8) as they will come from the decision tree. Shapes only, no numbers. */
export interface GoalPlan {
  id: string
  title: string
  summary: string
  /** Bars of the preview, as shares of the first year: [start, end] in 0–1. */
  mother: [number, number][]
  father: [number, number][]
}

export const GOAL_PLANS: GoalPlan[] = [
  {
    id: 'money',
    title: 'Najwięcej pieniędzy',
    summary: 'Mama bierze macierzyński i większość rodzicielskiego, tata swoje tygodnie na końcu.',
    mother: [[0.02, 0.86]],
    father: [[0.04, 0.08], [0.86, 1]],
  },
  {
    id: 'home',
    title: 'Najdłużej w domu',
    summary: 'Rodzice dzielą rodzicielski na części i łączą go z pracą na część etatu.',
    mother: [[0.02, 0.5], [0.62, 0.8]],
    father: [[0.04, 0.08], [0.5, 0.62], [0.8, 1]],
  },
  {
    id: 'equal',
    title: 'Równy podział',
    summary: 'Po macierzyńskim mama i tata biorą po połowie rodzicielskiego, jedno po drugim.',
    mother: [[0.02, 0.62]],
    father: [[0.04, 0.08], [0.62, 1]],
  },
]
