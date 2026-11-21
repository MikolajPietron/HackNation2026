import type { DocId, Lane, SourceRef } from '../types'
import { formatDate } from './dates'

export const LANE_ORDER: Record<Lane, number> = { child: 0, mother: 1, father: 2, applications: 3 }

/** Colour roles per lane, all from the ZUS palette tokens in index.css. */
export const LANE: Record<
  Lane,
  { label: string; initial: string; solid: string; soft: string; dot: string; text: string; chip: string }
> = {
  mother: {
    label: 'Mama',
    initial: 'M',
    solid: 'bg-zus-600 text-white',
    soft: 'bg-zus-200 text-zus-900',
    dot: 'bg-zus-600',
    text: 'text-zus-700',
    chip: 'bg-zus-50 text-zus-700 ring-zus-200',
  },
  father: {
    label: 'Tata',
    initial: 'T',
    solid: 'bg-navy-700 text-white',
    soft: 'bg-navy-200 text-navy-900',
    dot: 'bg-navy-700',
    text: 'text-navy-700',
    chip: 'bg-navy-50 text-navy-700 ring-navy-200',
  },
  child: {
    label: 'Ważny dzień',
    initial: '',
    solid: 'bg-sun-400 text-navy-900',
    soft: 'bg-sun-100 text-sun-700',
    dot: 'bg-sun-400',
    text: 'text-sun-700',
    chip: 'bg-sun-100 text-sun-700 ring-sun-300',
  },
  applications: {
    label: 'Wniosek',
    initial: '',
    solid: 'bg-sun-400 text-navy-900',
    soft: 'bg-sun-100 text-sun-700',
    dot: 'bg-sun-400',
    text: 'text-sun-700',
    chip: 'bg-sun-100 text-sun-700 ring-sun-300',
  },
}

const DOCS: Record<DocId, string> = {
  przewodnik: 'Przewodnik ZUS',
  kp: 'Kodeks pracy',
  ustawa: 'Ustawa zasiłkowa',
}

export function sourceLabel(source: SourceRef): string {
  const where = source.page ? `s. ${source.page}` : source.article
  return where ? `${DOCS[source.doc]}, ${where}` : DOCS[source.doc]
}

export const formatPercent = (value: number) => `${String(value).replace('.', ',')}%`

const asDate = (value: unknown) => (typeof value === 'string' ? formatDate(value) : '…')

/** Human label of an assistant tool call, shown as a step in the chat. */
export function toolLabel(name: string, args: Record<string, unknown>): string {
  switch (name) {
    case 'set_birth_date':
      return `${args.child_born ? 'Data urodzenia' : 'Termin porodu'}: ${asDate(args.birth_date)}`
    case 'set_children_count':
      return `Liczba dzieci: ${String(args.count)}`
    case 'set_maternity_leave_before_birth':
      return `Urlop przed porodem: ${String(args.weeks)} tyg.`
    case 'choose_benefit_variant':
      return args.flat_rate ? 'Wariant zasiłku: jedna stawka' : 'Wariant zasiłku: standardowy'
    case 'set_paternity_leave_start':
      return `Urlop ojcowski od ${asDate(args.start)}`
    case 'explain_timeline_element':
      return 'Pokazuję na osi czasu'
    case 'read_guide':
      return `Czytam Przewodnik ZUS, s. ${String(args.page)}`
    default:
      return name
  }
}

/** Tools whose result is visible on the timeline (the step can jump there). */
export const TIMELINE_TOOLS = new Set([
  'set_birth_date',
  'set_children_count',
  'set_maternity_leave_before_birth',
  'choose_benefit_variant',
  'set_paternity_leave_start',
  'explain_timeline_element',
])
