// What the calendar says about one day and about one month, read straight from the engine's
// timeline: the periods going on (who is at home), the important days, the documents due and the
// benefit coming in. Nothing here computes a date or an amount: it only picks what the engine
// already put on those days (CLAUDE.md: the engine counts, the UI shows).
import { dayNumber, formatShortDate } from './dates'
import { documentIcon, ICONS, markerIcon, segmentIcon } from './icons'
import { formatPln, formatRate } from './money'
import { deadlineOf, length, periodName } from './plan'
import type { Lane, Segment, Timeline } from '../types'

export type DayTone = 'mother' | 'father' | 'option-mother' | 'option-father' | 'work' | 'event' | 'document' | 'money'

export interface DayLine {
  key: string
  /** The element whose details a click opens. */
  id: string
  icon: string
  tone: DayTone
  /** "Mama", "Tata", "Ważny dzień", "Dokument", "Wpływa". */
  lead: string
  title: string
  rest: string
}

const WHO: Partial<Record<Lane, string>> = { mother: 'Mama', father: 'Tata' }

const segmentTone = (s: Segment): DayTone =>
  s.tone === 'work' ? 'work' : s.tone === 'option' ? (s.lane === 'father' ? 'option-father' : 'option-mother') : s.lane === 'father' ? 'father' : 'mother'

/** "dzień 3 z 14", "tydzień 5 z 20", "pierwszy dzień", "ostatni dzień". */
function progress(s: Segment, day: number): string {
  const elapsed = day - dayNumber(s.start) + 1
  if (elapsed === 1) return 'pierwszy dzień'
  if (day === dayNumber(s.end)) return 'ostatni dzień'
  return s.days % 7 === 0 ? `tydzień ${Math.ceil(elapsed / 7)} z ${s.days / 7}` : `dzień ${elapsed} z ${s.days}`
}

/** Everything the timeline has on one day, in the order a parent reads it. */
export function dayLines(timeline: Timeline, day: number): DayLine[] {
  const lines: DayLine[] = []
  const segments = [...timeline.segments].sort(
    (a, b) => (a.lane === b.lane ? 0 : a.lane === 'mother' ? -1 : 1) || a.start.localeCompare(b.start),
  )
  for (const s of segments) {
    if (dayNumber(s.start) > day || day > dayNumber(s.end)) continue
    const who = WHO[s.lane] ?? ''
    if (s.tone === 'option') {
      const deadline = deadlineOf(timeline, s)
      lines.push({
        key: `s-${s.id}`,
        id: s.id,
        icon: segmentIcon(s),
        tone: segmentTone(s),
        lead: who ? `${who} · do wyboru` : 'Do wyboru',
        title: periodName(s),
        rest: deadline ? `${length(s.days)} · najpóźniej do ${formatShortDate(deadline.date)}` : length(s.days),
      })
      continue
    }
    lines.push({
      key: `s-${s.id}`,
      id: s.id,
      icon: segmentIcon(s),
      tone: segmentTone(s),
      lead: who,
      title: s.title,
      rest: `${progress(s, day)} · do ${formatShortDate(s.end)}`,
    })
  }
  for (const m of timeline.markers) {
    if (dayNumber(m.date) !== day) continue
    lines.push({
      key: `m-${m.id}`,
      id: m.id,
      icon: markerIcon(m),
      tone: 'event',
      lead: m.irreversible ? 'Bez powrotu' : 'Ważny dzień',
      title: m.title,
      rest: m.irreversible?.lost ?? m.summary,
    })
  }
  for (const d of timeline.documents) {
    if (d.done) continue
    const due = dayNumber(d.needed_by) === day
    const deadline = d.deadline !== null && dayNumber(d.deadline) === day
    if (!due && !deadline) continue
    lines.push({
      key: `d-${d.id}`,
      id: d.id,
      icon: documentIcon(d),
      tone: 'document',
      lead: 'Dokument',
      title: d.title,
      rest: deadline ? 'ostatni dzień na złożenie' : 'na dzień startu',
    })
  }
  for (const p of timeline.payments) {
    if (dayNumber(p.start) > day || day > dayNumber(p.end)) continue
    const option = timeline.segments.find((s) => s.id === p.segment_id)?.tone === 'option'
    lines.push({
      key: `p-${p.id}`,
      id: p.id,
      icon: ICONS.pieniadze,
      tone: 'money',
      lead: option ? 'Gdy wybierzecie' : 'Wpływa',
      title: `${formatPln(p.monthly)} miesięcznie`,
      rest: `${p.lane === 'father' ? 'zasiłek taty' : 'zasiłek mamy'} · ${formatRate(p.rate)} · przed podatkiem`,
    })
  }
  return lines
}

export interface AgendaItem {
  key: string
  id: string
  day: number
  icon: string
  tone: 'event' | 'document' | 'start' | 'end' | 'option'
  title: string
}

/**
 * The month's days worth writing on a wall calendar: the important days, the documents due and
 * where each period begins and ends (a period running on into the next one of the same kind is
 * one period).
 */
export function monthAgenda(timeline: Timeline, from: number, to: number): AgendaItem[] {
  const items: AgendaItem[] = []
  const inMonth = (day: number) => day >= from && day <= to
  const segments = timeline.segments.filter((s) => s.tone !== 'work')
  const joined = (a: Segment, b: Segment) =>
    a.lane === b.lane && a.tone === b.tone && dayNumber(a.end) + 1 === dayNumber(b.start)
  const who = (s: Segment) => (WHO[s.lane] ? ` (${WHO[s.lane]!.toLowerCase()})` : '')
  for (const s of segments) {
    const start = dayNumber(s.start)
    const end = dayNumber(s.end)
    if (inMonth(start) && !segments.some((p) => joined(p, s))) {
      items.push({
        key: `start-${s.id}`,
        id: s.id,
        day: start,
        icon: segmentIcon(s),
        tone: s.tone === 'option' ? 'option' : 'start',
        title: s.tone === 'option' ? `Do wyboru: ${lower(periodName(s))}${who(s)}` : `Początek: ${lower(periodName(s))}${who(s)}`,
      })
    }
    if (s.tone !== 'option' && inMonth(end) && !segments.some((n) => joined(s, n))) {
      items.push({
        key: `end-${s.id}`,
        id: s.id,
        day: end,
        icon: segmentIcon(s),
        tone: 'end',
        title: `Koniec: ${lower(periodName(s))}${who(s)}`,
      })
    }
  }
  for (const m of timeline.markers) {
    const day = dayNumber(m.date)
    if (inMonth(day)) items.push({ key: `m-${m.id}`, id: m.id, day, icon: markerIcon(m), tone: 'event', title: m.title })
  }
  for (const d of timeline.documents) {
    if (d.done) continue
    const day = dayNumber(d.deadline ?? d.needed_by)
    if (inMonth(day)) items.push({ key: `d-${d.id}`, id: d.id, day, icon: documentIcon(d), tone: 'document', title: d.title })
  }
  const order = { event: 0, document: 1, start: 2, option: 3, end: 4 }
  return items.sort((a, b) => a.day - b.day || order[a.tone] - order[b.tone])
}

const lower = (text: string) => text.charAt(0).toLowerCase() + text.slice(1)
