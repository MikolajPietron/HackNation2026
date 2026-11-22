import type { Lane, PlanGoal, SourceRef, Tone, Work } from '../types'
import { formatDate } from './dates'
import { formatPln } from './money'

export const LANE_ORDER: Record<Lane, number> = { child: 0, mother: 1, father: 2, documents: 3 }

type Parent = 'mother' | 'father'

/** Classes of one kind of period. Colours are the ZUS tokens from index.css. */
interface ToneStyle {
  /** Chip in the list, e.g. "Urlop taty". */
  label: string
  pill: string
  /** The circle with the initial inside the pill. */
  avatar: string
  /** The dot on the list's line. */
  dot: string
  chip: string
  /** The legend's swatch. */
  swatch: string
  /** "Mama · urlop" over the details. */
  eyebrow: string
}

const PARENT: Record<Parent, { who: string; initial: string }> = {
  mother: { who: 'Mama', initial: 'M' },
  father: { who: 'Tata', initial: 'T' },
}

const KIND: Record<Tone, string> = { leave: 'urlop', option: 'do wyboru', work: 'praca' }

/**
 * Green is the mother, navy the father. A filled pill is a leave; a light one (the father's:
 * outlined) is a period still to decide; the grey-blue one is work.
 */
const STYLE: Record<Parent, Record<Tone, ToneStyle>> = {
  mother: {
    leave: {
      label: 'Urlop',
      pill: 'bg-zus-600 text-white',
      avatar: 'bg-white/20',
      dot: 'bg-zus-600',
      chip: 'bg-zus-50 text-zus-700 ring-zus-200',
      swatch: 'bg-zus-600',
      eyebrow: 'text-zus-700',
    },
    option: {
      label: 'Do wyboru',
      pill: 'bg-zus-200 text-zus-900',
      avatar: 'bg-white',
      dot: 'bg-zus-300',
      chip: 'bg-zus-50 text-zus-700 ring-zus-200',
      swatch: 'bg-zus-200',
      eyebrow: 'text-zus-700',
    },
    work: {
      label: 'Praca',
      pill: 'bg-navy-200 text-navy-900',
      avatar: 'bg-white',
      dot: 'bg-navy-400',
      chip: 'bg-navy-50 text-navy-700 ring-navy-200',
      swatch: 'bg-navy-200',
      eyebrow: 'text-navy-500',
    },
  },
  father: {
    leave: {
      label: 'Urlop taty',
      pill: 'bg-navy-700 text-white',
      avatar: 'bg-white/20',
      dot: 'bg-navy-700',
      chip: 'bg-navy-700 text-white ring-navy-700',
      swatch: 'bg-navy-700',
      eyebrow: 'text-navy-700',
    },
    // An outline keeps it apart from work (filled grey-blue) and from the mother's option.
    option: {
      label: 'Do wyboru',
      pill: 'bg-navy-50 text-navy-900 inset-ring-2 inset-ring-navy-500',
      avatar: 'bg-navy-700 text-white',
      dot: 'bg-white inset-ring-2 inset-ring-navy-500',
      chip: 'bg-white text-navy-700 ring-navy-400',
      swatch: 'bg-navy-50 inset-ring-2 inset-ring-navy-500',
      eyebrow: 'text-navy-700',
    },
    work: {
      label: 'Praca taty',
      pill: 'bg-navy-200 text-navy-900',
      avatar: 'bg-white',
      dot: 'bg-navy-400',
      chip: 'bg-navy-50 text-navy-700 ring-navy-200',
      swatch: 'bg-navy-200',
      eyebrow: 'text-navy-500',
    },
  },
}

export type SegmentLook = ToneStyle & {
  /** Whose period: "Mama" or "Tata". */
  who: string
  initial: string
  /** What kind of period, in lower case: "urlop", "do wyboru", "praca". */
  kind: string
}

/** How a period looks: by whose it is (the father's lane, else the mother's) and what it is. */
export function segmentLook({ lane, tone }: { lane: Lane; tone: Tone }): SegmentLook {
  const parent: Parent = lane === 'father' ? 'father' : 'mother'
  return { ...PARENT[parent], kind: KIND[tone], ...STYLE[parent][tone] }
}

/**
 * The acts the app quotes besides the guide, as their labels start. The two regulations are
 * quoted by the request forms (`Document.form`, ZADANIA B.3).
 */
type LawDoc = 'kp' | 'ustawa' | 'rozp_wnioski' | 'rozp_zasilki'
const LAW_NAME: Record<LawDoc, string> = {
  kp: 'Kodeks pracy',
  ustawa: 'Ustawa zasiłkowa',
  rozp_wnioski: 'Rozporządzenie w sprawie wniosków urlopowych',
  rozp_zasilki: 'Rozporządzenie w sprawie dokumentów do zasiłków',
}
const LAW_DOCS: LawDoc[] = ['kp', 'ustawa', 'rozp_wnioski', 'rozp_zasilki']

const pagesOf = (source: SourceRef) => `s. ${source.page}${source.page_to ? `–${source.page_to}` : ''}`

export const sourceLabel = (source: SourceRef) =>
  source.doc === 'przewodnik'
    ? `Przewodnik ZUS, ${pagesOf(source)}`
    : source.doc === 'poradnik'
      ? `Poradnik ZUS 2026, ${pagesOf(source)}`
      : source.doc === 'zalacznik'
        ? `Załącznik ZUS, ${source.section}`
        : `${LAW_NAME[source.doc]}, ${source.article}`

/**
 * Where a set of quotes comes from, in one short line: the guide's pages and the articles of
 * the Labour Code and the ustawa zasiłkowa (without paragraphs), e.g. "Przewodnik ZUS, s. 5–7 ·
 * Kodeks pracy, art. 182¹ᵃ, 182¹ᶜ · Ustawa zasiłkowa, art. 31", the paragraphs of the two
 * regulations ("Rozporządzenie w sprawie wniosków urlopowych, § 15"), the ZUS Załącznik and the
 * pages of the ZUS Poradnik ("Poradnik ZUS 2026, s. 34").
 */
export function sourcesSummary(sources: SourceRef[]): string {
  const pages = new Set<number>()
  const poradnik = new Set<number>()
  const articles: Record<LawDoc, Set<string>> = {
    kp: new Set(),
    ustawa: new Set(),
    rozp_wnioski: new Set(),
    rozp_zasilki: new Set(),
  }
  let zalacznik = false
  for (const source of sources) {
    if (source.doc === 'zalacznik') {
      zalacznik = true
    } else if (source.doc === 'poradnik') {
      if (source.page !== null) {
        for (let page = source.page; page <= (source.page_to ?? source.page); page++) poradnik.add(page)
      }
    } else if (source.doc !== 'przewodnik') {
      if (source.article) {
        articles[source.doc].add(
          source.article.replace(/^art\. /, '').replace(/ (§|ust\.|pkt) .*$/, ''),
        )
      }
    } else if (source.page !== null) {
      for (let page = source.page; page <= (source.page_to ?? source.page); page++) pages.add(page)
    }
  }
  const parts = []
  if (pages.size > 0) parts.push(`Przewodnik ZUS, s. ${pageRanges([...pages])}`)
  for (const doc of LAW_DOCS) {
    if (articles[doc].size === 0) continue
    const kind = doc === 'kp' || doc === 'ustawa' ? 'art. ' : ''
    parts.push(`${LAW_NAME[doc]}, ${kind}${[...articles[doc]].join(', ')}`)
  }
  if (zalacznik) parts.push('Załącznik ZUS')
  if (poradnik.size > 0) parts.push(`Poradnik ZUS 2026, s. ${pageRanges([...poradnik])}`)
  return parts.join(' · ')
}

/** [3, 5, 6, 7, 10] -> "3, 5–7, 10" */
function pageRanges(pages: number[]): string {
  const sorted = [...pages].sort((a, b) => a - b)
  const ranges: string[] = []
  for (let i = 0; i < sorted.length; i++) {
    let end = i
    while (end + 1 < sorted.length && sorted[end + 1] === sorted[end] + 1) end++
    ranges.push(end > i ? `${sorted[i]}–${sorted[end]}` : `${sorted[i]}`)
    i = end
  }
  return ranges.join(', ')
}

export const WORK_LABEL: Record<Work, string> = {
  employment: 'na etacie (umowa o pracę)',
  contract: 'na umowie zlecenia',
  business: 'własna firma (JDG)',
  none: 'nie pracuje',
}

/** The goals of planning parental leave (F8, backend engine/plans.py `GOAL_LABEL`). */
export const PLAN_GOAL_LABEL: Record<PlanGoal, string> = {
  'most-money': 'najwięcej pieniędzy',
  'longest-home': 'najdłużej w domu',
  'equal-split': 'równy podział',
  'quick-return': 'szybki powrót do pracy',
}

/** "jedno dziecko", "bliźnięta", "trojaczki", "4 dzieci" — for headers. */
export function childrenLabel(count: number): string {
  return { 1: 'jedno dziecko', 2: 'bliźnięta', 3: 'trojaczki' }[count] ?? `${count} dzieci`
}

const asDate = (value: unknown) => (typeof value === 'string' ? formatDate(value) : '…')

/** Human label of an assistant tool call, shown as a step in the chat. */
export function toolLabel(name: string, args: Record<string, unknown>): string {
  switch (name) {
    case 'set_due_date':
      return `Termin porodu: ${asDate(args.due_date)}`
    case 'set_birth_date':
      return `Data urodzenia: ${asDate(args.birth_date)}`
    case 'set_children_count':
      return typeof args.count === 'number'
        ? `Liczba dzieci: ${childrenLabel(args.count)}`
        : 'Liczba dzieci'
    case 'set_leave_before_birth':
      return args.weeks === 0
        ? 'Bez urlopu przed porodem'
        : `Urlop przed porodem: ${String(args.weeks)} tyg.`
    case 'set_medical_certificate':
      return args.has_certificate
        ? 'Zaświadczenie lekarskie: jest'
        : 'Zaświadczenie lekarskie: do zdobycia'
    case 'set_mother_work':
      return `Praca mamy: ${WORK_LABEL[args.work as Work] ?? '…'}`
    case 'set_voluntary_insurance':
      return args.registered
        ? 'Dobrowolne ubezpieczenie chorobowe: jest'
        : 'Dobrowolne ubezpieczenie chorobowe: brak'
    case 'set_za_zyciem':
      return args.has_certificate
        ? 'Zaświadczenie „Za życiem”: jest'
        : 'Zaświadczenie „Za życiem”: brak'
    // Hard news (the child's death, the mother's situation): a neutral step, no details.
    case 'set_child_loss':
    case 'set_mother_situation':
      return 'Uwzględniam to na osi czasu'
    case 'set_hospital_care':
      return args.applies ? 'Wcześniak albo pobyt w szpitalu' : 'Bez pobytu w szpitalu'
    case 'set_father_work':
      return `Praca taty: ${WORK_LABEL[args.work as Work] ?? '…'}`
    case 'set_father_insurance':
      return args.registered ? 'Dobrowolne chorobowe taty: jest' : 'Dobrowolne chorobowe taty: brak'
    case 'set_father_takeover':
      if (!args.takes_over) return 'Bez przejęcia urlopu przez tatę'
      return typeof args.mother_weeks === 'number'
        ? `Tata przejmuje urlop macierzyński po ${args.mother_weeks} tyg.`
        : 'Tata przejmuje urlop macierzyński'
    case 'set_payer_size': {
      const whose = args.parent === 'father' ? 'taty' : 'mamy'
      if (args.size === 'over-20') return `Zasiłek ${whose} wypłaca pracodawca`
      if (args.size === 'up-to-20') return `Zasiłek ${whose} wypłaca ZUS`
      return `Kto wypłaca zasiłek ${whose}: do sprawdzenia`
    }
    // Guide section D: a child taken in for upbringing.
    case 'set_taken_in':
      if (args.kind === 'adoption') return 'Adopcja dziecka'
      if (args.kind === 'foster') return 'Rodzina zastępcza'
      return 'Dziecko urodzone w rodzinie'
    case 'set_school_postponed':
      return args.postponed
        ? 'Odroczony obowiązek szkolny'
        : 'Bez odroczenia obowiązku szkolnego'
    case 'set_adoption_ruling':
      return args.final
        ? `Przysposobienie prawomocne: ${asDate(args.final_on)}`
        : 'Przysposobienie jeszcze nieprawomocne'
    case 'set_leave_handover':
      return args.handed_over
        ? 'Dalszą część urlopu przejmuje drugi rodzic'
        : 'Urlop bez przekazania drugiemu rodzicowi'
    case 'set_foster_before':
      return args.used_leave
        ? 'Najpierw rodzina zastępcza, potem adopcja'
        : 'Bez wcześniejszej rodziny zastępczej'
    case 'set_rehab_benefit':
      if (args.status === 'granted') return 'Świadczenie rehabilitacyjne przyznane'
      if (args.status === 'refused') return 'Świadczenie rehabilitacyjne nieprzyznane'
      return args.status === 'applied'
        ? 'Wniosek o świadczenie rehabilitacyjne'
        : 'Świadczenie rehabilitacyjne'
    case 'set_monthly_pay': {
      const whose = args.parent === 'father' ? 'taty' : 'mamy'
      return typeof args.amount === 'number'
        ? `Kwota ${whose}: ${formatPln(args.amount)} miesięcznie`
        : `Kwota ${whose}: nie podano`
    }
    case 'set_pay_history': {
      const whose = args.parent === 'father' ? 'taty' : 'mamy'
      const months = Array.isArray(args.months) ? args.months.length : 0
      return months > 0 ? `Zarobki ${whose}: ${months} mies.` : `Dane do podstawy zasiłku ${whose}`
    }
    case 'set_rate_choice':
      if (args.rate_815 === true) return 'Zasiłek 81,5% przez cały urlop'
      return args.rate_815 === false ? 'Zasiłek 100% i 70%' : 'Wybór zasiłku: jeszcze nie'
    case 'explain_timeline_element':
      return 'Pokazuję na osi czasu'
    case 'set_sick_leave':
      return args.on_sick_leave
        ? `Zwolnienie lekarskie od ${asDate(args.start)}`
        : 'Bez zwolnienia lekarskiego w ciąży'
    case 'set_insured_since':
      return typeof args.since === 'string'
        ? `Ubezpieczenie chorobowe od ${asDate(args.since)}`
        : 'Ubezpieczenie chorobowe'
    case 'set_mother_over_50':
      return 'Wiek mamy'
    // Losing the job and the risks of section H: a neutral step, no details.
    case 'set_job_loss':
    case 'set_contribution_base_raised':
      return 'Uwzględniam to na osi czasu'
    case 'set_parental_plan':
      return Array.isArray(args.parts) && args.parts.length === 0
        ? 'Bez planu urlopu rodzicielskiego'
        : 'Plan urlopu rodzicielskiego'
    case 'set_parental_work': {
      const who = args.parent === 'father' ? 'taty' : 'mamy'
      return typeof args.work_fraction === 'string'
        ? `Praca ${who} w czasie urlopu rodzicielskiego: ${args.work_fraction} etatu`
        : `Bez pracy ${who} w czasie urlopu rodzicielskiego`
    }
    // F8 plans for a goal and F11 the stress test: computed by the engine, nothing changes.
    case 'propose_plans':
      return `Układam plany: ${PLAN_GOAL_LABEL[args.goal as PlanGoal] ?? 'Wasz cel'}`
    case 'stress_test':
      return 'Sprawdzam, co zmieniłoby się w planie'
    default:
      return name
  }
}

/** Polish plural: 1 tydzień, 2 tygodnie, 5 tygodni. */
export function plural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one
  const last = n % 10
  const lastTwo = n % 100
  return last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? few : many
}
