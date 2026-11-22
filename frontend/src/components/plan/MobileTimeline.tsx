// The plan's timeline on phones: one vertical line, everything in date order, months as
// headings, "Dziś" where today falls. Same picture standards as the wide timeline: events on a
// tile on the line, hints as a small icon. Tapping an element opens its details with the source.
import { Fragment } from 'react'
import { motion } from 'motion/react'
import { ITEM } from '@/components/onboarding/motion'
import { Emphasis } from '@/components/ui/emphasis'
import { Illustration } from '@/components/ui/illustration'
import { dayNumber, durationLabel, formatDayMonthShort, isoFromDay } from '@/lib/dates'
import { documentIcon, isKeyMarker, markerIcon, segmentIcon } from '@/lib/icons'
import { formatPln, formatRate, paymentFor } from '@/lib/money'
import { cn } from '@/lib/utils'
import type { Segment, Timeline } from '@/types'
import { NoReturnTag } from './NextSteps'

interface Row {
  id: string
  day: number
  icon: string
  key: boolean
  title: string
  when: string
  text: string
  tone?: Segment['tone']
  lane?: Segment['lane']
  /** Section G: what the period pays a month, when the engine computed it. */
  money?: string
  /** A point of no return (FUNKCJE F10). */
  locked?: boolean
}

/** The coloured edge of a period: green for the mother, navy for the father. */
const TONE_BAR: Record<'mother' | 'father', Record<Segment['tone'], string>> = {
  mother: { leave: 'bg-zus-600', option: 'bg-zus-200', work: 'bg-navy-200' },
  father: { leave: 'bg-navy-700', option: 'bg-navy-200', work: 'bg-navy-200' },
}

const monthTitle = new Intl.DateTimeFormat('pl-PL', { month: 'long', year: 'numeric', timeZone: 'UTC' })

function rows(timeline: Timeline): Row[] {
  return [
    ...timeline.segments.map((s) => ({
      id: s.id,
      day: dayNumber(s.start),
      icon: segmentIcon(s),
      key: true,
      title: s.title,
      when: `${formatDayMonthShort(s.start)} – ${formatDayMonthShort(s.end)} · ${durationLabel(s.days)}`,
      text: s.summary,
      tone: s.tone,
      lane: s.lane,
      money: moneyLine(timeline, s.id),
    })),
    ...timeline.markers.map((m) => ({
      id: m.id,
      day: dayNumber(m.date),
      icon: markerIcon(m),
      key: isKeyMarker(m),
      title: m.title,
      when: formatDayMonthShort(m.date),
      text: m.summary,
      locked: m.irreversible !== null && m.irreversible.days_left >= 0,
    })),
    ...timeline.documents.map((d) => ({
      id: d.id,
      day: dayNumber(d.needed_by),
      icon: documentIcon(d),
      key: !d.done,
      title: d.done ? `${d.title} — już jest` : d.title,
      when: `potrzebne na ${formatDayMonthShort(d.needed_by)}`,
      text: d.rule,
    })),
  ].sort((a, b) => a.day - b.day)
}

export function MobileTimeline({
  timeline,
  changedIds,
  changeVersion,
  selectedId,
  onSelect,
}: {
  timeline: Timeline
  changedIds: Set<string>
  changeVersion: number
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const today = dayNumber(timeline.today)
  const list = rows(timeline)
  const todayIndex = list.findIndex((row) => row.day > today)
  const insertAt = todayIndex === -1 ? list.length : todayIndex
  const month = (day: number) => monthTitle.format(new Date(`${isoFromDay(day)}T00:00:00Z`))

  return (
    <div>
      <ol className="relative">
        <span aria-hidden className="absolute top-2 bottom-2 left-[17px] w-0.5 rounded-full bg-line" />
        {list.map((row, index) => {
          const newMonth = index === 0 || month(list[index - 1].day) !== month(row.day)
          return (
            <Fragment key={row.id}>
              {index === insertAt && <TodayLine iso={timeline.today} />}
              {newMonth && (
                <li className="relative pt-4 pb-1 pl-12 text-xs font-bold tracking-wide text-navy-400 first-letter:uppercase">
                  {month(row.day)}
                </li>
              )}
              <motion.li variants={ITEM} className="relative flex gap-3 py-1.5">
                <span className="relative z-10 grid w-9 shrink-0 place-items-start justify-center pt-2">
                  {row.key ? (
                    <Illustration src={row.icon} size="event" className="ring-4 ring-white" />
                  ) : (
                    <span className="grid size-9 place-items-center rounded-full bg-white">
                      <Illustration src={row.icon} size="hint" />
                    </span>
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => onSelect(row.id)}
                  className={cn(
                    'relative min-w-0 flex-1 overflow-hidden rounded-2xl border px-4 py-3 text-left',
                    'transition-[border-color,background-color,transform] duration-150 active:scale-[0.98]',
                    'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                    row.key && !row.tone ? 'border-sun-300 bg-sun-100/50' : 'border-line bg-white',
                    selectedId === row.id && 'border-navy-300',
                  )}
                >
                  {row.tone && (
                    <span aria-hidden className={cn(
                        'absolute inset-y-0 left-0 w-1.5',
                        TONE_BAR[row.lane === 'father' ? 'father' : 'mother'][row.tone],
                      )} />
                  )}
                  {changedIds.has(row.id) && (
                    <motion.span
                      key={changeVersion}
                      initial={{ opacity: 1 }}
                      animate={{ opacity: 0 }}
                      transition={{ duration: 1.6, ease: 'easeOut' }}
                      className="absolute inset-0 rounded-[inherit] ring-4 ring-sun-300 ring-inset"
                    />
                  )}
                  <span className="block text-xs font-bold text-zus-700">{row.when}</span>
                  <span
                    className={cn(
                      'mt-0.5 block leading-snug text-navy-900',
                      row.key ? 'font-bold' : 'text-sm font-bold text-navy-700',
                    )}
                  >
                    {row.title}
                  </span>
                  {row.locked && (
                    <span className="mt-1 block">
                      <NoReturnTag />
                    </span>
                  )}
                  {row.money && (
                    <span className="mt-1 inline-block rounded-full bg-sun-100 px-2 py-0.5 text-xs font-bold text-sun-700">
                      {row.money}
                    </span>
                  )}
                  {row.key && (
                    <span className="mt-1 block text-sm leading-relaxed text-navy-500">
                      <Emphasis text={row.text} className="text-navy-700" />
                    </span>
                  )}
                </button>
              </motion.li>
            </Fragment>
          )
        })}
        {insertAt === list.length && <TodayLine iso={timeline.today} />}
      </ol>
    </div>
  )
}

function moneyLine(timeline: Timeline, segmentId: string): string | undefined {
  const payment = paymentFor(timeline, segmentId)
  return payment && `Zasiłek ${formatPln(payment.monthly)}/mies. · ${formatRate(payment.rate)}`
}

function TodayLine({ iso }: { iso: string }) {
  return (
    <li className="relative flex items-center gap-3 py-2" aria-label="Dziś">
      <span className="relative z-10 grid w-9 shrink-0 place-items-center">
        <span className="size-3 rounded-full border-2 border-white bg-navy-900 ring-2 ring-navy-900" />
      </span>
      <span className="h-0.5 flex-1 bg-navy-900" />
      <span className="rounded-full bg-navy-900 px-2.5 py-1 text-xs font-bold text-white">
        Dziś · {formatDayMonthShort(iso)}
      </span>
    </li>
  )
}
