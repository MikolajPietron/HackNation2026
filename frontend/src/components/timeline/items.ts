import { dayNumber } from '../../lib/dates'
import type { Application, Lane, Marker, Segment, Timeline } from '../../types'

interface ItemBase {
  id: string
  lane: Lane
  label: string
  title: string
  start: string
  startDay: number
  endDay: number
}

/** Segments, markers and applications in one shape, for drawing. */
export type TimelineItem =
  | (ItemBase & { kind: 'segment'; element: Segment })
  | (ItemBase & { kind: 'marker'; element: Marker })
  | (ItemBase & { kind: 'application'; element: Application })

export function timelineItems(timeline: Timeline): TimelineItem[] {
  return [
    ...timeline.segments.map(
      (s): TimelineItem => ({
        kind: 'segment',
        element: s,
        id: s.id,
        lane: s.lane,
        label: s.title,
        title: s.title,
        start: s.start,
        startDay: dayNumber(s.start),
        endDay: dayNumber(s.end),
      }),
    ),
    ...timeline.markers.map(
      (m): TimelineItem => ({
        kind: 'marker',
        element: m,
        id: m.id,
        lane: m.lane,
        label: m.label,
        title: m.title,
        start: m.date,
        startDay: dayNumber(m.date),
        endDay: dayNumber(m.date),
      }),
    ),
    ...timeline.applications.map(
      (a): TimelineItem => ({
        kind: 'application',
        element: a,
        id: a.id,
        lane: 'applications',
        label: a.label,
        title: a.title,
        start: a.due,
        startDay: dayNumber(a.due),
        endDay: dayNumber(a.due),
      }),
    ),
  ]
}

/** What the timeline views share: selection, highlighted changes and assistant focus. */
export interface TimelineViewProps {
  timeline: Timeline
  items: TimelineItem[]
  selectedId: string | null
  changedIds: Set<string>
  changeVersion: number
  focus: { id: string | null; tick: number }
  onSelect: (id: string | null) => void
}
