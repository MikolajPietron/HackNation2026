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
const monthFormat = new Intl.DateTimeFormat('pl-PL', { month: 'short', timeZone: 'UTC' })

export const formatDate = (iso: string) => shortFormat.format(toDate(dayNumber(iso)))
export const formatLongDate = (iso: string) => longFormat.format(toDate(dayNumber(iso)))
export const formatRange = (start: string, end: string) => `${formatDate(start)} – ${formatDate(end)}`

export function durationLabel(days: number): string {
  return days % 7 === 0 ? `${days / 7} tyg. (${days} dni)` : `${days} dni`
}

export interface MonthTick {
  day: number
  label: string
  year: number | null
}

/** First day of every month between two day numbers; `year` is set on January ticks. */
export function monthTicks(fromDay: number, toDay: number): MonthTick[] {
  const first = toDate(fromDay)
  let year = first.getUTCFullYear()
  let month = first.getUTCMonth() + 1
  const ticks: MonthTick[] = []
  for (;;) {
    if (month > 11) {
      year += 1
      month = 0
    }
    const day = Date.UTC(year, month, 1) / DAY_MS
    if (day > toDay) return ticks
    ticks.push({ day, label: monthFormat.format(toDate(day)), year: month === 0 ? year : null })
    month += 1
  }
}
