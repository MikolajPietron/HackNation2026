import type { DocId, Lane, SourceRef } from '../types'
import { formatDate } from './dates'

export const cx = (...classes: (string | false | null | undefined)[]) =>
  classes.filter(Boolean).join(' ')

export const LANES: Lane[] = ['mother', 'father', 'child', 'applications']

export const LANE_ORDER: Record<Lane, number> = { child: 0, mother: 1, father: 2, applications: 3 }

export const LANE: Record<
  Lane,
  { label: string; bar: string; dot: string; chip: string; text: string }
> = {
  mother: {
    label: 'Mama',
    bar: 'border-rose-300 bg-rose-100 text-rose-950',
    dot: 'bg-rose-500',
    chip: 'bg-rose-50 text-rose-800 ring-rose-200',
    text: 'text-rose-700',
  },
  father: {
    label: 'Tata',
    bar: 'border-sky-300 bg-sky-100 text-sky-950',
    dot: 'bg-sky-500',
    chip: 'bg-sky-50 text-sky-800 ring-sky-200',
    text: 'text-sky-700',
  },
  child: {
    label: 'Dziecko i terminy',
    bar: 'border-amber-300 bg-amber-100 text-amber-950',
    dot: 'bg-amber-500',
    chip: 'bg-amber-50 text-amber-800 ring-amber-200',
    text: 'text-amber-700',
  },
  applications: {
    label: 'Wnioski',
    bar: 'border-violet-300 bg-violet-100 text-violet-950',
    dot: 'bg-violet-500',
    chip: 'bg-violet-50 text-violet-800 ring-violet-200',
    text: 'text-violet-700',
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

/** Human label of an assistant tool call, shown as a chip in the chat. */
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

/** Tools whose result is visible on the timeline (the chip can jump there). */
export const TIMELINE_TOOLS = new Set([
  'set_birth_date',
  'set_children_count',
  'set_maternity_leave_before_birth',
  'choose_benefit_variant',
  'set_paternity_leave_start',
  'explain_timeline_element',
])
