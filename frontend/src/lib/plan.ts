// What the plan screen says about a timeline, read straight from the engine's output: the
// headline, the family's leave in total, the windows of the periods still to decide, and the
// steps ahead. Nothing here computes a date or a length: it only picks, groups and words what
// the engine already computed (CLAUDE.md: the engine counts, the UI shows).
import { dayNumber, formatDistance, formatLongDate, formatShortDate } from './dates'
import { documentIcon, markerIcon, segmentIcon } from './icons'
import type { CaseNote, Marker, Segment, Timeline } from '../types'

/** Periods that are a part of another one, not extra leave (the weeks before the birth come
 *  out of the 20 weeks of maternity leave). */
const PART_OF_ANOTHER = new Set(['prenatal-window'])

/** The last day a period still to decide can be taken, as the engine marks it. */
const DEADLINE_OF: Record<string, string> = {
  paternity: 'paternity-deadline',
  parental: 'parental-deadline',
  'parental-father': 'parental-deadline',
}

/** Periods whose window runs up to the deadline; drawn as a window on the timeline. A parental
 *  leave's deadline is years away, so it is not drawn as a window. */
const WINDOWED = new Set(['paternity'])

/** "Urlop rodzicielski — do wyboru" -> "Urlop rodzicielski". */
export const periodName = (segment: Segment) => segment.title.replace(/\s+[—–-]\s+do wyboru$/i, '')

/** The name on a clip, where the track already says whose it is: "Rodzicielski", "Ojcowski". */
export function clipName(segment: Segment): string {
  const name = periodName(segment)
    .replace(/^Urlop\s+/i, '')
    .replace(/\s+taty$/i, '')
  return name.charAt(0).toUpperCase() + name.slice(1)
}

/** "20 tyg."; short periods in days, as the guide says them ("14 dni"). */
export const length = (days: number) =>
  days % 7 === 0 && days >= 21 ? `${days / 7} tyg.` : `${days} ${days === 1 ? 'dzień' : 'dni'}`

export function deadlineOf(timeline: Timeline, segment: Segment): Marker | undefined {
  const id = DEADLINE_OF[segment.id]
  return id ? timeline.markers.find((m) => m.id === id) : undefined
}

/** The window a period still to decide can be taken in, when it is worth drawing. */
export function optionWindow(timeline: Timeline, segment: Segment): Marker | undefined {
  return segment.tone === 'option' && WINDOWED.has(segment.id) ? deadlineOf(timeline, segment) : undefined
}

// ---------------------------------------------------------------------------------------------
// Headline

/** "na urlopie …" for the periods we have words for; others fall back to their title. */
const ON_LEAVE: Record<string, string> = {
  'maternity-prenatal': 'urlopie macierzyńskim',
  maternity: 'urlopie macierzyńskim',
  parental: 'urlopie rodzicielskim',
  'parental-father': 'urlopie rodzicielskim',
  paternity: 'urlopie ojcowskim',
}

const WHO: Record<string, string> = { mother: 'Mama', father: 'Tata' }

const listJoin = (items: string[]) =>
  items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} i ${items.at(-1)}`

const lower = (text: string) => text.charAt(0).toLowerCase() + text.slice(1)

/**
 * The plan in one line, and a second line with what is still to decide. Today's leave comes
 * first ("Mama jest na urlopie macierzyńskim do 23 marca 2027"); before the birth, the due date.
 */
export function headline(timeline: Timeline): { title: string; text: string } {
  const today = dayNumber(timeline.today)
  const sorted = [...timeline.segments].sort((a, b) => a.start.localeCompare(b.start))
  const active = sorted.filter(
    (s) => s.tone === 'leave' && dayNumber(s.start) <= today && today <= dayNumber(s.end),
  )

  const titles = active.map((s) => {
    const words = ON_LEAVE[s.id]
    // The period goes on in the next one of the same kind (before and after the birth).
    let end = s.end
    for (const next of sorted) {
      if (next.lane === s.lane && next.tone === 'leave' && ON_LEAVE[next.id] === words &&
        dayNumber(next.start) === dayNumber(end) + 1) end = next.end
    }
    return words
      ? `${WHO[s.lane] ?? ''} jest na ${words} do ${formatLongDate(end)}`.trim()
      : `${periodName(s)} trwa do ${formatLongDate(end)}`
  })
  const title =
    titles.length > 0
      ? titles.join(' · ')
      : timeline.child_born
        ? `Dziecko urodziło się ${formatLongDate(timeline.birth_date)}`
        : `Termin porodu: ${formatLongDate(timeline.birth_date)}`

  const parts: string[] = []
  // Before the birth (or before the leave starts) the length of the maternity leave is the news.
  if (active.length === 0) {
    const maternity = sorted.filter((s) => s.lane === 'mother' && s.tone === 'leave')
    if (maternity.length > 0) {
      const days = maternity.reduce((sum, s) => sum + s.days, 0)
      parts.push(
        `${periodName(maternity[0]).replace(/ (przed|po) porodzie$/, '')}: ${length(days)}, ` +
          `od ${formatLongDate(maternity[0].start)} do ${formatLongDate(maternity.at(-1)!.end)}.`,
      )
    }
  }
  const options = sorted.filter((s) => s.tone === 'option' && dayNumber(s.end) >= today)
  if (options.length > 0) {
    parts.push(
      `Do wyboru: ${listJoin(options.map((s) => `${lower(periodName(s))} (${length(s.days)})`))}.`,
    )
  }
  return { title, text: parts.join(' ') }
}

// ---------------------------------------------------------------------------------------------
// Leave in total

export interface Budget {
  totalDays: number
  mother: Segment[]
  father: Segment[]
}

/** All the leave the family has on the timeline, taken or to decide, per parent. */
export function leaveBudget(timeline: Timeline): Budget {
  const counted = timeline.segments
    .filter((s) => s.tone !== 'work' && !PART_OF_ANOTHER.has(s.id))
    .sort((a, b) => a.start.localeCompare(b.start))
  const mother = counted.filter((s) => s.lane === 'mother')
  const father = counted.filter((s) => s.lane === 'father')
  const totalDays = [...mother, ...father].reduce((sum, s) => sum + s.days, 0)
  return { totalDays, mother, father }
}

// ---------------------------------------------------------------------------------------------
// The way into the explanation

/** Whether the family is entitled, as the case explanation says. */
export function entitlement(notes: CaseNote[]): CaseNote | undefined {
  return notes.find((n) => n.id === 'insurance')
}

// ---------------------------------------------------------------------------------------------
// Steps ahead

export type StepGroup = 'now' | 'soon' | 'later'

export interface Step {
  key: string
  /** The element whose details a click opens. */
  id: string
  date: string
  title: string
  detail: string
  icon: string
  decide: boolean
  overdue: boolean
}

const NOW_DAYS = 14
const SOON_DAYS = 92

/**
 * What lies ahead, in date order: the periods still to decide, the first and last days of
 * leave, the important days and the documents to get. Past days are left out: the timeline
 * shows them.
 */
export function nextSteps(timeline: Timeline): Record<StepGroup, Step[]> {
  const today = dayNumber(timeline.today)
  const steps: (Step & { day: number; group?: StepGroup })[] = []
  const sorted = [...timeline.segments].sort((a, b) => a.start.localeCompare(b.start))
  const joined = (a: Segment, b: Segment) =>
    a.lane === b.lane && a.tone === 'leave' && b.tone === 'leave' &&
    dayNumber(a.end) + 1 === dayNumber(b.start)

  for (const s of sorted) {
    const start = dayNumber(s.start)
    const end = dayNumber(s.end)
    if (s.tone === 'option') {
      if (end < today) continue
      const deadline = deadlineOf(timeline, s)
      const open = start <= today
      steps.push({
        key: `decide-${s.id}`,
        id: s.id,
        day: open ? today : start,
        date: open ? timeline.today : s.start,
        title: periodName(s),
        detail: deadline
          ? `${length(s.days)} · najpóźniej do ${formatShortDate(deadline.date)}`
          : `${length(s.days)} · od ${formatShortDate(s.start)}`,
        icon: segmentIcon(s),
        decide: true,
        overdue: false,
        group: open ? 'now' : undefined,
      })
      continue
    }
    if (s.tone !== 'leave') continue
    if (start > today && !sorted.some((p) => joined(p, s))) {
      steps.push({
        key: `start-${s.id}`,
        id: s.id,
        day: start,
        date: s.start,
        title: `Pierwszy dzień: ${lower(periodName(s))}`,
        detail: formatDistance(timeline.today, s.start),
        icon: segmentIcon(s),
        decide: false,
        overdue: false,
      })
    }
    if (end >= today && !sorted.some((n) => joined(s, n))) {
      steps.push({
        key: `end-${s.id}`,
        id: s.id,
        day: end,
        date: s.end,
        title: `Ostatni dzień: ${lower(periodName(s)).replace(/ po porodzie$/, '')}`,
        detail: formatDistance(timeline.today, s.end),
        icon: segmentIcon(s),
        decide: false,
        overdue: false,
      })
    }
  }
  for (const m of timeline.markers) {
    const day = dayNumber(m.date)
    if (day < today) continue
    steps.push({
      key: `marker-${m.id}`,
      id: m.id,
      day,
      date: m.date,
      title: m.title,
      detail: formatDistance(timeline.today, m.date),
      icon: markerIcon(m),
      decide: false,
      overdue: false,
    })
  }
  for (const d of timeline.documents) {
    if (d.done) continue
    const day = dayNumber(d.needed_by)
    const overdue = day < today
    steps.push({
      key: `document-${d.id}`,
      id: d.id,
      day: overdue ? today : day,
      date: d.needed_by,
      title: `Przygotuj: ${lower(d.title)}`,
      detail: overdue ? `termin minął ${formatShortDate(d.needed_by)}` : `potrzebne ${formatDistance(timeline.today, d.needed_by)}`,
      icon: documentIcon(d),
      decide: false,
      overdue,
      group: overdue ? 'now' : undefined,
    })
  }

  const groups: Record<StepGroup, Step[]> = { now: [], soon: [], later: [] }
  for (const step of steps.sort((a, b) => a.day - b.day || Number(b.decide) - Number(a.decide))) {
    const group =
      step.group ?? (step.day - today <= NOW_DAYS ? 'now' : step.day - today <= SOON_DAYS ? 'soon' : 'later')
    groups[group].push(step)
  }
  return groups
}
