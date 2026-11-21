import type { Lane, SourceRef, Tone, Work } from '../types'
import { formatDate } from './dates'

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

export const sourceLabel = (source: SourceRef) =>
  source.doc === 'kp'
    ? `Kodeks pracy, ${source.article}`
    : `Przewodnik ZUS, s. ${source.page}${source.page_to ? `–${source.page_to}` : ''}`

/**
 * Where a set of quotes comes from, in one short line: the guide's pages and the Labour Code's
 * articles (without paragraphs), e.g. "Przewodnik ZUS, s. 5–7 · Kodeks pracy, art. 182¹ᵃ, 182¹ᶜ".
 */
export function sourcesSummary(sources: SourceRef[]): string {
  const pages = new Set<number>()
  const articles = new Set<string>()
  for (const source of sources) {
    if (source.doc === 'kp') {
      if (source.article) articles.add(source.article.replace(/^art\. /, '').replace(/ § .*$/, ''))
    } else if (source.page !== null) {
      for (let page = source.page; page <= (source.page_to ?? source.page); page++) pages.add(page)
    }
  }
  const parts = []
  if (pages.size > 0) parts.push(`Przewodnik ZUS, s. ${pageRanges([...pages])}`)
  if (articles.size > 0) parts.push(`Kodeks pracy, art. ${[...articles].join(', ')}`)
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
    case 'explain_timeline_element':
      return 'Pokazuję na osi czasu'
    default:
      return name
  }
}
