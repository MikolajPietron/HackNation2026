// Display helpers only. Legal dates are computed by the backend engine, never here.

const DAY_MS = 86_400_000

/** Day number (days since 1970-01-01) of an ISO date, independent of the browser's time zone. */
export function dayNumber(iso: string): number {
  const [year, month, day] = iso.split('-').map(Number)
  return Date.UTC(year, month - 1, day) / DAY_MS
}

const toDate = (day: number) => new Date(day * DAY_MS)

const shortFormat = new Intl.DateTimeFormat('pl-PL', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: 'UTC',
})
const longFormat = new Intl.DateTimeFormat('pl-PL', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})
const dayMonthFormat = new Intl.DateTimeFormat('pl-PL', {
  day: '2-digit',
  month: '2-digit',
  timeZone: 'UTC',
})
const monthFormat = new Intl.DateTimeFormat('pl-PL', { month: 'short', timeZone: 'UTC' })

export const formatDate = (iso: string) => shortFormat.format(toDate(dayNumber(iso)))
export const formatLongDate = (iso: string) => longFormat.format(toDate(dayNumber(iso)))
/** Day and month only, e.g. 15.03 — for tight labels on the axis. */
export const formatDayMonth = (iso: string) => dayMonthFormat.format(toDate(dayNumber(iso)))
export const formatRange = (start: string, end: string) => `${formatDate(start)} – ${formatDate(end)}`

export function durationLabel(days: number): string {
  return days % 7 === 0 ? `${days / 7} tyg. (${days} dni)` : `${days} dni`
}

export interface MonthCell {
  /** First and last day number of the month. */
  start: number
  end: number
  label: string
  year: number
}

/** Every calendar month that overlaps the range between two day numbers. */
export function monthCells(fromDay: number, toDay: number): MonthCell[] {
  const first = toDate(fromDay)
  let year = first.getUTCFullYear()
  let month = first.getUTCMonth()
  const cells: MonthCell[] = []
  for (;;) {
    const start = Date.UTC(year, month, 1) / DAY_MS
    if (start > toDay) return cells
    const end = Date.UTC(year, month + 1, 1) / DAY_MS - 1
    cells.push({ start, end, label: monthFormat.format(toDate(start)), year })
    month += 1
    if (month > 11) {
      year += 1
      month = 0
    }
  }
}
