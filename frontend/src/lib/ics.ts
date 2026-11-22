// A calendar file (iCalendar, RFC 5545) with the family's deadlines, to add to the phone's or the
// computer's calendar (FUNKCJE F25): the steps ahead (requests and their deadlines, first and last
// days of leave, points of no return) or what is left on the table. All-day events on the
// engine's dates, each with a reminder a week before, the rule and its source in the description,
// no personal data. Display only: the dates are the engine's, nothing is computed here.
import { dayNumber, isoFromDay } from './dates'
import { nextSteps } from './plan'
import { sourcesSummary } from './ui'
import type { SourceRef, Timeline } from '../types'

export interface CalendarEvent {
  uid: string
  /** ISO date of the all-day event. */
  date: string
  title: string
  description: string
}

const escape = (text: string) =>
  text.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n')

const compact = (iso: string) => iso.replaceAll('-', '')

/** Lines longer than 75 octets are folded (RFC 5545 3.1); Polish letters take two octets. */
function fold(line: string): string {
  const parts: string[] = []
  let rest = line
  while (rest.length > 60) {
    parts.push(rest.slice(0, 60))
    rest = rest.slice(60)
  }
  parts.push(rest)
  return parts.join('\r\n ')
}

export function calendarFile(events: CalendarEvent[]): string {
  const stamp = `${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}Z`
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Zasilkowy Przewodnik Rodzica//PL',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
  ]
  for (const event of events) {
    lines.push(
      'BEGIN:VEVENT',
      `UID:${event.uid}-${compact(event.date)}@przewodnik-rodzica`,
      `DTSTAMP:${stamp}`,
      `DTSTART;VALUE=DATE:${compact(event.date)}`,
      `DTEND;VALUE=DATE:${compact(isoFromDay(dayNumber(event.date) + 1))}`,
      `SUMMARY:${escape(event.title)}`,
      `DESCRIPTION:${escape(event.description)}`,
      'TRANSP:TRANSPARENT',
      'BEGIN:VALARM',
      'TRIGGER:-P7D',
      'ACTION:DISPLAY',
      `DESCRIPTION:${escape(event.title)}`,
      'END:VALARM',
      'END:VEVENT',
    )
  }
  lines.push('END:VCALENDAR')
  return lines.map(fold).join('\r\n') + '\r\n'
}

/** Saves the file through the browser's download. */
export function downloadCalendar(name: string, events: CalendarEvent[]): void {
  const blob = new Blob([calendarFile(events)], { type: 'text/calendar;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${name}.ics`
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Every step ahead on the plan ("Co przed Wami") as a calendar event, with its rule and source. */
export function planEvents(timeline: Timeline): CalendarEvent[] {
  const groups = nextSteps(timeline)
  return [...groups.now, ...groups.soon, ...groups.later].map((step) => {
    const segment = timeline.segments.find((s) => s.id === step.id)
    const marker = timeline.markers.find((m) => m.id === step.id)
    const document = timeline.documents.find((d) => d.id === step.id)
    const rule = document?.rule ?? marker?.irreversible?.lost ?? marker?.summary ?? segment?.summary ?? ''
    const sources: SourceRef[] = document?.sources ?? marker?.sources ?? segment?.sources ?? []
    const source = sources.length > 0 ? `Źródło: ${sourcesSummary(sources)}.` : ''
    return {
      uid: step.key,
      date: step.date,
      title: step.decide ? `Do wyboru: ${step.title}` : step.title,
      description: [rule, source].filter(Boolean).join(' '),
    }
  })
}
