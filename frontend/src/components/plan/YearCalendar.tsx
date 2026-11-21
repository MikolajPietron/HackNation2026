// The plan as a wall calendar: every month of the leave, each day coloured by who is at home
// (green the mother, navy the father; light when still to decide), important days ringed in
// amber, today in navy. The question it answers at a glance: "when are we with the baby?".
// Pick a day and the readout under the months says what happens then.
import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { dayNumber, isoFromDay, monthCells } from '@/lib/dates'
import { cn } from '@/lib/utils'
import type { Segment, Timeline } from '@/types'
import { Readout } from './Readout'

const WEEKDAYS = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd']
const monthTitle = new Intl.DateTimeFormat('pl-PL', { month: 'long', year: 'numeric', timeZone: 'UTC' })
/** Months shown at most; the far deadlines are on the axis and in "Co przed Wami". */
const MAX_MONTHS = 18

type Fill = 'motherLeave' | 'motherOption' | 'fatherLeave' | 'fatherOption'

const COLOR: Record<Fill, string> = {
  motherLeave: 'var(--color-zus-600)',
  motherOption: 'var(--color-zus-100)',
  fatherLeave: 'var(--color-navy-700)',
  fatherOption: 'var(--color-navy-100)',
}

const LEGEND: { fill: Fill; label: string }[] = [
  { fill: 'motherLeave', label: 'Mama · urlop' },
  { fill: 'motherOption', label: 'Mama · do wyboru' },
  { fill: 'fatherLeave', label: 'Tata · urlop' },
  { fill: 'fatherOption', label: 'Tata · do wyboru' },
]

const fillOf = (s: Segment): Fill | null =>
  s.tone === 'work' ? null : `${s.lane === 'father' ? 'father' : 'mother'}${s.tone === 'leave' ? 'Leave' : 'Option'}` as Fill

/** Monday = 0. 1970-01-01 was a Thursday. */
const weekday = (day: number) => (((day + 3) % 7) + 7) % 7

export function YearCalendar({
  timeline,
  onSelect,
}: {
  timeline: Timeline
  onSelect: (id: string) => void
}) {
  const today = dayNumber(timeline.today)
  const [picked, setPicked] = useState(today)

  const { months, fills, marked } = useMemo(() => {
    const fills = new Map<number, Fill[]>()
    for (const s of timeline.segments) {
      const fill = fillOf(s)
      if (!fill) continue
      for (let day = dayNumber(s.start); day <= dayNumber(s.end); day += 1) {
        const list = fills.get(day) ?? []
        if (!list.includes(fill)) list.push(fill)
        fills.set(day, list)
      }
    }
    const marked = new Set(timeline.markers.map((m) => dayNumber(m.date)))
    for (const d of timeline.documents) if (!d.done) marked.add(dayNumber(d.needed_by))
    const periodDays = timeline.segments.flatMap((s) => [dayNumber(s.start), dayNumber(s.end)])
    const first = Math.min(today, dayNumber(timeline.birth_date), ...periodDays)
    const last = Math.max(today, dayNumber(timeline.birth_date), ...periodDays)
    return { months: monthCells(first, last).slice(0, MAX_MONTHS), fills, marked }
  }, [timeline, today])

  const present = new Set([...fills.values()].flat())

  return (
    <div>
      <ul className="mb-4 flex flex-wrap gap-x-4 gap-y-1.5 text-xs font-bold text-navy-500">
        {LEGEND.filter((item) => present.has(item.fill)).map((item) => (
          <li key={item.fill} className="flex items-center gap-1.5">
            <span className="size-3 rounded" style={{ background: COLOR[item.fill] }} />
            {item.label}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span className="size-3 rounded ring-2 ring-sun-400 ring-inset" />
          ważny dzień
        </li>
        <li className="flex items-center gap-1.5">
          <span className="size-3 rounded ring-2 ring-navy-900 ring-inset" />
          dziś
        </li>
      </ul>

      <div className="grid grid-cols-1 gap-x-6 gap-y-5 min-[420px]:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
        {months.map((month) => {
          const blanks = weekday(month.start)
          const days = Array.from({ length: month.end - month.start + 1 }, (_, i) => month.start + i)
          return (
            <section key={month.start} aria-label={monthTitle.format(new Date(`${isoFromDay(month.start)}T00:00:00Z`))}>
              <h4 className="mb-1.5 text-sm font-bold text-navy-900 first-letter:uppercase">
                {monthTitle.format(new Date(`${isoFromDay(month.start)}T00:00:00Z`))}
              </h4>
              <div className="grid grid-cols-7 gap-0.5 text-center">
                {WEEKDAYS.map((name) => (
                  <span key={name} className="pb-0.5 text-[10px] font-bold text-navy-400">
                    {name}
                  </span>
                ))}
                {Array.from({ length: blanks }, (_, i) => (
                  <span key={`b-${i}`} />
                ))}
                {days.map((day) => {
                  const list = fills.get(day) ?? []
                  const solid = list.some((fill) => fill.endsWith('Leave'))
                  const style: CSSProperties =
                    list.length === 0
                      ? {}
                      : list.length === 1
                        ? { background: COLOR[list[0]] }
                        : { background: `linear-gradient(135deg, ${COLOR[list[0]]} 50%, ${COLOR[list[1]]} 50%)` }
                  return (
                    <button
                      key={day}
                      type="button"
                      onClick={() => setPicked(day)}
                      aria-pressed={picked === day}
                      aria-label={isoFromDay(day)}
                      className={cn(
                        'grid aspect-square place-items-center rounded-md text-[11px] font-bold tabular-nums transition-transform duration-100 active:scale-90',
                        solid ? 'text-white' : list.length ? 'text-navy-900' : 'text-navy-500 hover:bg-navy-50',
                        marked.has(day) && 'ring-2 ring-sun-400 ring-inset',
                        day === today && 'ring-2 ring-navy-900 ring-inset',
                        picked === day && 'outline-2 outline-offset-1 outline-navy-900',
                      )}
                      style={style}
                    >
                      {day - month.start + 1}
                    </button>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>

      <Readout timeline={timeline} day={picked} onSelect={onSelect} onHover={() => undefined} />
    </div>
  )
}
