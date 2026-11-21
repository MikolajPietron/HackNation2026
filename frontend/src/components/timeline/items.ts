import { dayNumber } from '@/lib/dates'
import type { Document, Lane, Marker, Segment, Timeline } from '@/types'

interface ItemBase {
  id: string
  lane: Lane
  label: string
  title: string
  start: string
  startDay: number
  endDay: number
}

/** Segments, markers and documents in one shape, for drawing. */
export type TimelineItem =
  | (ItemBase & { kind: 'segment'; element: Segment })
  | (ItemBase & { kind: 'marker'; element: Marker })
  | (ItemBase & { kind: 'document'; element: Document })

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
    ...timeline.documents.map(
      (d): TimelineItem => ({
        kind: 'document',
        element: d,
        id: d.id,
        lane: 'documents',
        label: d.label,
        title: d.title,
        start: d.needed_by,
        startDay: dayNumber(d.needed_by),
        endDay: dayNumber(d.needed_by),
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
