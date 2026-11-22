// What changed on the timeline, in words a parent reads at a glance, for the banner over the axis
// after every recalculation ("Plan się zmienił"). It compares two timelines of the engine element
// by element: a period added, gone, longer or moved; an important day or a request added or
// moved; a monthly amount that changed. Nothing is computed: lengths, dates and amounts are the
// engine's, put side by side.
import { formatShortDate } from './dates'
import { documentIcon, ICONS, markerIcon, segmentIcon } from './icons'
import { formatPln } from './money'
import { length, periodName } from './plan'
import type { Lane, Segment, Timeline } from '../types'

export type ChangeKind = 'added' | 'removed' | 'moved' | 'money'

export interface ChangeItem {
  key: string
  /** The element whose details a click opens; null when it is gone from the plan. */
  id: string | null
  kind: ChangeKind
  icon: string
  title: string
  detail: string
  /** The first day it concerns, to put the playhead on. */
  date: string | null
}

const WHO: Partial<Record<Lane, string>> = { mother: 'Mama', father: 'Tata' }
const who = (lane: Lane) => (WHO[lane] ? `${WHO[lane]}: ` : '')
const lower = (text: string) => text.charAt(0).toLowerCase() + text.slice(1)

const ORDER: Record<ChangeKind, number> = { added: 0, removed: 1, moved: 2, money: 3 }

function segmentChange(before: Segment | undefined, after: Segment | undefined): ChangeItem | null {
  if (after && !before) {
    return {
      key: `s-${after.id}`,
      id: after.id,
      kind: 'added',
      icon: segmentIcon(after),
      title: `${who(after.lane)}${lower(periodName(after))}`,
      detail: `${length(after.days)}${after.tone === 'option' ? ', do wyboru' : ''} · od ${formatShortDate(after.start)}`,
      date: after.start,
    }
  }
  if (before && !after) {
    return {
      key: `s-${before.id}`,
      id: null,
      kind: 'removed',
      icon: segmentIcon(before),
      title: `${who(before.lane)}${lower(periodName(before))}`,
      detail: 'znika z planu',
      date: null,
    }
  }
  if (!before || !after) return null
  if (before.start === after.start && before.end === after.end && before.tone === after.tone) return null
  const detail =
    before.days !== after.days
      ? `${length(before.days)} → ${length(after.days)}`
      : before.tone !== after.tone
        ? after.tone === 'option'
          ? 'znów do wyboru'
          : 'zaplanowany'
        : `od ${formatShortDate(before.start)} → od ${formatShortDate(after.start)}`
  return {
    key: `s-${after.id}`,
    id: after.id,
    kind: 'moved',
    icon: segmentIcon(after),
    title: `${who(after.lane)}${lower(periodName(after))}`,
    detail,
    date: after.start,
  }
}

/**
 * The changes between two timelines. `ids` are the elements the engine (or the plan change)
 * marked as changed; periods that are gone are found by comparing, since a removed element is
 * not on the new timeline to be marked.
 */
export function describeChange(before: Timeline, after: Timeline, ids: string[]): ChangeItem[] {
  const marked = new Set(ids)
  const items: ChangeItem[] = []
  const segmentIds = new Set([...before.segments, ...after.segments].map((s) => s.id))
  const changedSegments = new Set<string>()
  for (const id of segmentIds) {
    const old = before.segments.find((s) => s.id === id)
    const now = after.segments.find((s) => s.id === id)
    if (now && !marked.has(id) && old) continue
    const item = segmentChange(old, now)
    if (item) {
      items.push(item)
      changedSegments.add(id)
    }
  }
  for (const m of after.markers) {
    if (!marked.has(m.id)) continue
    const old = before.markers.find((o) => o.id === m.id)
    if (old && old.date === m.date) continue
    items.push({
      key: `m-${m.id}`,
      id: m.id,
      kind: old ? 'moved' : 'added',
      icon: markerIcon(m),
      title: m.title,
      detail: old ? `${formatShortDate(old.date)} → ${formatShortDate(m.date)}` : formatShortDate(m.date),
      date: m.date,
    })
  }
  for (const d of after.documents) {
    if (!marked.has(d.id) || d.done) continue
    const old = before.documents.find((o) => o.id === d.id)
    // A request that only moves with its period says nothing new.
    if (old && d.segment_id && changedSegments.has(d.segment_id)) continue
    const day = d.deadline ?? d.needed_by
    const oldDay = old ? (old.deadline ?? old.needed_by) : null
    if (oldDay === day) continue
    items.push({
      key: `d-${d.id}`,
      id: d.id,
      kind: old ? 'moved' : 'added',
      icon: documentIcon(d),
      title: d.title,
      detail: oldDay ? `${formatShortDate(oldDay)} → ${formatShortDate(day)}` : `na ${formatShortDate(day)}`,
      date: day,
    })
  }
  for (const p of after.payments) {
    if (!marked.has(p.id)) continue
    const old = before.payments.find((o) => o.id === p.id)
    if (old && old.monthly === p.monthly) continue
    if (!old && changedSegments.has(p.segment_id)) continue
    items.push({
      key: `p-${p.id}`,
      id: p.id,
      kind: 'money',
      icon: ICONS.pieniadze,
      title: p.title,
      detail: old ? `${formatPln(old.monthly)} → ${formatPln(p.monthly)} / mies.` : `${formatPln(p.monthly)} / mies.`,
      date: p.start,
    })
  }
  return items.sort((a, b) => ORDER[a.kind] - ORDER[b.kind] || (a.date ?? '').localeCompare(b.date ?? ''))
}

/** The first day a change concerns on the new timeline, for the playhead. */
export function firstChangedDay(timeline: Timeline, ids: string[]): string | null {
  const marked = new Set(ids)
  const days = [
    ...timeline.segments.filter((s) => marked.has(s.id)).map((s) => s.start),
    ...timeline.markers.filter((m) => marked.has(m.id)).map((m) => m.date),
    ...timeline.payments.filter((p) => marked.has(p.id)).map((p) => p.start),
    ...timeline.documents.filter((d) => marked.has(d.id) && !d.done).map((d) => d.deadline ?? d.needed_by),
  ].sort()
  return days.find((day) => day >= timeline.today) ?? days[0] ?? null
}
