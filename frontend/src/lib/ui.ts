import type { Lane, SourceRef, Tone } from '../types'
import { formatDate } from './dates'

export const LANE_ORDER: Record<Lane, number> = { child: 0, mother: 1, documents: 2 }

/** How a segment looks, by what it means. Colours are the ZUS tokens from index.css. */
export const TONE: Record<Tone, { label: string; pill: string; avatar: string; dot: string; chip: string }> = {
  leave: {
    label: 'Urlop',
    pill: 'bg-zus-600 text-white',
    avatar: 'bg-white/20',
    dot: 'bg-zus-600',
    chip: 'bg-zus-50 text-zus-700 ring-zus-200',
  },
  option: {
    label: 'Do wyboru',
    pill: 'bg-zus-200 text-zus-900',
    avatar: 'bg-white',
    dot: 'bg-zus-300',
    chip: 'bg-zus-50 text-zus-700 ring-zus-200',
  },
  work: {
    label: 'Praca',
    pill: 'bg-navy-200 text-navy-900',
    avatar: 'bg-white',
    dot: 'bg-navy-400',
    chip: 'bg-navy-50 text-navy-700 ring-navy-200',
  },
}

export const sourceLabel = (source: SourceRef) =>
  source.doc === 'kp' ? `Kodeks pracy, ${source.article}` : `Przewodnik ZUS, s. ${source.page}`

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
    case 'explain_timeline_element':
      return 'Pokazuję na osi czasu'
    default:
      return name
  }
}
