// What happens on one day (the playhead's, a day picked in the calendar, or today on phones), in
// a few bold facts. A period still to decide is never told as if it were going on: it says what
// can be chosen and until when.
import { Illustration } from '@/components/ui/illustration'
import { dayNumber, formatDayMonthShort, formatDistance, formatShortDate, isoFromDay } from '@/lib/dates'
import { documentIcon, markerIcon, segmentIcon } from '@/lib/icons'
import { ICONS } from '@/lib/icons'
import { formatPln, formatRate } from '@/lib/money'
import { deadlineOf, length, optionWindow, periodName } from '@/lib/plan'
import type { Segment, Timeline } from '@/types'

const weekdayDate = new Intl.DateTimeFormat('pl-PL', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})

interface Line {
  key: string
  id: string
  icon: string
  lead?: string
  title: string
  rest: string
}

/** The last day a period to decide can still be taken: its window's end, else its own end. */
const lastDay = (timeline: Timeline, s: Segment) => {
  const window = optionWindow(timeline, s)
  return window ? dayNumber(window.date) : dayNumber(s.end)
}

export function Readout({
  timeline,
  day,
  onSelect,
  onHover,
}: {
  timeline: Timeline
  day: number
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
}) {
  const iso = isoFromDay(day)
  const byStart = [...timeline.segments].sort((a, b) => a.start.localeCompare(b.start))
  const active = byStart.filter(
    (s) => dayNumber(s.start) <= day && day <= (s.tone === 'option' ? lastDay(timeline, s) : dayNumber(s.end)),
  )
  const upcoming = byStart.find((s) => dayNumber(s.start) > day)
  const markersToday = timeline.markers.filter((m) => dayNumber(m.date) === day)
  const nextMarker = [...timeline.markers]
    .filter((m) => dayNumber(m.date) > day)
    .sort((a, b) => a.date.localeCompare(b.date))[0]
  const nextDocument = [...timeline.documents]
    .filter((d) => !d.done && dayNumber(d.needed_by) >= day)
    .sort((a, b) => a.needed_by.localeCompare(b.needed_by))[0]

  const lines: Line[] = []
  for (const s of active) {
    if (s.tone === 'option') {
      const deadline = deadlineOf(timeline, s)
      lines.push({
        key: `o-${s.id}`,
        id: s.id,
        icon: segmentIcon(s),
        lead: 'Do wyboru',
        title: periodName(s),
        rest: deadline
          ? `${length(s.days)} · najpóźniej do ${formatShortDate(deadline.date)}`
          : `${length(s.days)} · ${formatDayMonthShort(s.start)} – ${formatDayMonthShort(s.end)}`,
      })
      continue
    }
    const elapsed = day - dayNumber(s.start) + 1
    const progress =
      s.days % 7 === 0 ? `tydzień ${Math.ceil(elapsed / 7)} z ${s.days / 7}` : `dzień ${elapsed} z ${s.days}`
    lines.push({
      key: `a-${s.id}`,
      id: s.id,
      icon: segmentIcon(s),
      title: s.title,
      rest: `${progress} · do ${formatDayMonthShort(s.end)}`,
    })
  }
  // What comes in on that day: the benefit of each period going on, as the engine computed it.
  for (const p of timeline.payments) {
    if (dayNumber(p.start) > day || day > dayNumber(p.end)) continue
    // A period still to decide pays only if it is taken: say so, as for the period itself.
    const option = timeline.segments.find((s) => s.id === p.segment_id)?.tone === 'option'
    lines.push({
      key: `p-${p.id}`,
      id: p.id,
      icon: ICONS.pieniadze,
      lead: option ? 'Do wyboru' : 'Wpływa',
      title: `${formatPln(p.monthly)} miesięcznie`,
      rest: `${p.lane === 'father' ? 'zasiłek taty' : 'zasiłek mamy'} · ${formatRate(p.rate)}`,
    })
  }
  if (active.length === 0 && upcoming) {
    lines.push({
      key: `u-${upcoming.id}`,
      id: upcoming.id,
      icon: segmentIcon(upcoming),
      lead: upcoming.tone === 'option' ? 'Potem do wyboru' : 'Następnie',
      title: upcoming.tone === 'option' ? periodName(upcoming) : upcoming.title,
      rest: `${formatDistance(iso, upcoming.start)} · ${formatDayMonthShort(upcoming.start)}`,
    })
  }
  for (const m of markersToday) {
    lines.push({ key: `t-${m.id}`, id: m.id, icon: markerIcon(m), title: m.title, rest: 'tego dnia' })
  }
  if (nextMarker) {
    lines.push({
      key: `n-${nextMarker.id}`,
      id: nextMarker.id,
      icon: markerIcon(nextMarker),
      lead: 'Najbliższy ważny dzień',
      title: nextMarker.title,
      rest: `${formatDistance(iso, nextMarker.date)} · ${formatShortDate(nextMarker.date)}`,
    })
  }
  if (nextDocument) {
    lines.push({
      key: `d-${nextDocument.id}`,
      id: nextDocument.id,
      icon: documentIcon(nextDocument),
      lead: 'Dokument',
      title: nextDocument.title,
      rest: `potrzebny ${formatDistance(iso, nextDocument.needed_by)} · ${formatDayMonthShort(nextDocument.needed_by)}`,
    })
  }

  const label = weekdayDate.format(new Date(`${iso}T00:00:00Z`))
  const comma = label.indexOf(', ')
  return (
    <div
      className="mt-3 flex flex-col gap-3 rounded-3xl bg-navy-50/60 px-4 py-4 sm:flex-row sm:gap-6 sm:px-5"
      aria-live="polite"
    >
      <div className="shrink-0 sm:w-44">
        <p className="text-xs font-bold text-navy-500 capitalize">{label.slice(0, comma)}</p>
        <p className="mt-0.5 text-lg leading-tight font-bold text-navy-900">{label.slice(comma + 2)}</p>
        <p className="mt-0.5 text-sm text-navy-500">{formatDistance(timeline.today, iso)}</p>
      </div>
      <ul className="-mx-2 min-w-0 flex-1 space-y-0.5 sm:mx-0">
        {lines.length === 0 && <li className="pt-1 text-navy-500">Tego dnia nic się nie zmienia.</li>}
        {lines.map((line) => (
          <li key={line.key}>
            <button
              type="button"
              onClick={() => onSelect(line.id)}
              onMouseEnter={() => onHover(line.id)}
              onMouseLeave={() => onHover(null)}
              className="flex w-full items-center gap-2.5 rounded-xl px-2 py-1 text-left transition-colors duration-150 hover:bg-white"
            >
              <Illustration src={line.icon} size="hint" />
              <span className="min-w-0">
                {line.lead && <span className="text-navy-500">{line.lead}: </span>}
                <span className="font-bold text-navy-900">{line.title}</span>
                <span className="text-navy-400"> · </span>
                <span className="font-bold text-zus-700">{line.rest}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
