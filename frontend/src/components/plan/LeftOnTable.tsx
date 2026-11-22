// "Nie zostawiajcie tego na stole" (FUNKCJE F9): what the family can still use and loses if it
// does nothing, the soonest first, as the engine lists it (`Timeline.left_on_table`). One card
// each: whose right, what, how much (the engine's amount; the screen never adds anything up) and
// the window it can still be used in, drawn to scale from the engine's dates: the dark end is the
// latest the whole of it still fits. Each card leads to doing something about it: fill in the
// request (the form the engine prepared for that period), choose 81,5% (with undo), open its
// details (the title), or put the deadline into the parent's own calendar (an .ics file with a
// reminder).
import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { CalendarPlus, Check, ChevronRight, FilePenLine, Scale } from 'lucide-react'
import { Illustration } from '@/components/ui/illustration'
import type { PlanApply } from '@/hooks/usePlanChange'
import { dayNumber, formatDistance, formatShortDate } from '@/lib/dates'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { downloadCalendar } from '@/lib/ics'
import type { CalendarEvent } from '@/lib/ics'
import { ICONS, segmentIcon } from '@/lib/icons'
import { formatPln } from '@/lib/money'
import { COUNTDOWN_DAYS, daysLeftLabel, length } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { Leftover, Scenario, Timeline } from '@/types'
import { NoReturnTag } from './NextSteps'

const WHO: Record<'mother' | 'father' | 'both', { label: string; dot: string; whose: string }> = {
  mother: { label: 'Mama', dot: 'bg-zus-600', whose: 'mama' },
  father: { label: 'Tata', dot: 'bg-navy-700', whose: 'tata' },
  both: { label: 'Mama albo tata', dot: 'bg-sun-400', whose: 'mama albo tata' },
}

/** The event to put into the parent's calendar: the last day to start, or the last day at all. */
function calendarEvent(item: Leftover): CalendarEvent {
  const who = WHO[item.parent ?? 'both'].whose
  if (item.kind === 'choice') {
    return {
      uid: item.id,
      date: item.last_day,
      title: `Ostatni dzień: ${item.title.toLowerCase()} (${who})`,
      description: item.text,
    }
  }
  return item.start_by
    ? {
        uid: item.id,
        date: item.start_by,
        title: `Ostatni dzień, żeby zacząć: ${item.title.toLowerCase()} (${who})`,
        description: `${item.text} Żeby wykorzystać całość, trzeba zacząć najpóźniej tego dnia.`,
      }
    : {
        uid: item.id,
        date: item.last_day,
        title: `Ostatni dzień: ${item.title.toLowerCase()} (${who})`,
        description: item.text,
      }
}

const fileName = (text: string) =>
  text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/ł/g, 'l')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')

export function LeftOnTable({
  timeline,
  scenario,
  onSelect,
  onFill,
  onApply,
  onCompare,
}: {
  timeline: Timeline
  scenario: Scenario | null
  onSelect: (id: string) => void
  /** Open the request form of a document. */
  onFill: (documentId: string) => void
  /** Change the plan from the interface (with undo). */
  onApply: PlanApply
  /** Show the comparison of 100% + 70% and 81,5%. */
  onCompare: () => void
}) {
  const items = timeline.left_on_table
  if (items.length === 0) return null
  return (
    <section aria-labelledby="left-on-table" className="rounded-4xl border border-line px-4 pt-5 pb-4 sm:px-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <Illustration src={ICONS.skarbonka} size="event" className="bg-sun-100/70" />
          <div className="min-w-0 flex-1">
            <h2 id="left-on-table" className="text-lg leading-tight font-bold text-navy-900">
              Nie zostawiajcie tego na stole
            </h2>
            <p className="mt-0.5 text-sm text-navy-500">To jeszcze Wam przysługuje. Jeśli nic nie zrobicie, przepadnie.</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => downloadCalendar('terminy-urlopow', items.map(calendarEvent))}
          className="flex h-9 shrink-0 items-center gap-2 self-start rounded-full border border-line px-3.5 text-sm font-bold text-navy-700 transition-[border-color,background-color] duration-150 hover:border-navy-200 hover:bg-navy-50"
        >
          <CalendarPlus className="size-4" />
          Wszystkie terminy do kalendarza
        </button>
      </header>
      <ul className="mt-4 grid gap-3 lg:grid-cols-2">
        {items.map((item, index) => (
          <Card
            key={item.id}
            item={item}
            index={index}
            timeline={timeline}
            scenario={scenario}
            onSelect={onSelect}
            onFill={onFill}
            onApply={onApply}
            onCompare={onCompare}
          />
        ))}
      </ul>
    </section>
  )
}

function Card({
  item,
  index,
  timeline,
  scenario,
  onSelect,
  onFill,
  onApply,
  onCompare,
}: {
  item: Leftover
  index: number
  timeline: Timeline
  scenario: Scenario | null
  onSelect: (id: string) => void
  onFill: (documentId: string) => void
  onApply: PlanApply
  onCompare: () => void
}) {
  const segment = timeline.segments.find((s) => s.id === item.segment_id)
  const marker = timeline.markers.find((m) => m.id === item.marker_id)
  const target = segment?.id ?? marker?.id ?? null
  const who = WHO[item.parent ?? 'both']
  const icon = segment ? segmentIcon(segment) : item.kind === 'choice' ? ICONS.pieniadze : ICONS.kalendarz
  const left = marker?.irreversible?.days_left
  const countdown =
    left !== undefined && left >= 0 && left <= COUNTDOWN_DAYS
      ? daysLeftLabel(left)
      : formatDistance(timeline.today, item.start_by ?? item.last_day)
  const urgent = left !== undefined && left >= 0 && left <= COUNTDOWN_DAYS
  const amount = item.amount !== null && item.amount > 0 ? item.amount : null
  // The request the engine prepared for this period (a form to fill in).
  const request = item.segment_id
    ? timeline.documents.find((d) => d.segment_id === item.segment_id && d.form !== null && !d.done)
    : undefined
  const chose815 = scenario?.rate_815 === true

  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, delay: Math.min(index, 6) * 0.05, ease: EASE_OUT }}
      className={cn(
        'flex flex-col rounded-3xl border bg-white p-4 transition-[border-color,box-shadow] duration-200 hover:shadow-[0_16px_40px_-28px_rgb(26_36_56/0.4)]',
        urgent ? 'border-sun-300' : 'border-line hover:border-navy-100',
      )}
    >
      <div className="flex items-start gap-3">
        <Illustration src={icon} size="event" className="bg-navy-50/60" />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="flex items-center gap-1.5 text-xs font-bold text-navy-500">
              <span className={cn('size-2 rounded-full', who.dot)} aria-hidden />
              {who.label}
            </span>
            {marker?.irreversible && <NoReturnTag />}
            {item.kind === 'choice' && (
              <span className="rounded-full bg-zus-50 px-2 py-0.5 text-[11px] font-bold text-zus-700">wybór</span>
            )}
          </p>
          {target ? (
            <button
              type="button"
              onClick={() => onSelect(target)}
              className="group mt-1 flex items-center gap-0.5 rounded-md text-left leading-tight font-bold text-navy-900 underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
            >
              {item.title}
              <ChevronRight className="size-4 shrink-0 text-navy-300 transition-transform group-hover:translate-x-0.5 group-hover:text-navy-500" />
            </button>
          ) : (
            <h3 className="mt-1 leading-tight font-bold text-navy-900">{item.title}</h3>
          )}
        </div>
        <div className="shrink-0 text-right">
          {amount !== null ? (
            <p className="text-xl leading-tight font-bold text-navy-900 tabular-nums">
              {item.kind === 'choice' && '+'}
              {formatPln(amount)}
            </p>
          ) : item.days !== null ? (
            <p className="text-xl leading-tight font-bold text-navy-900">{length(item.days)}</p>
          ) : null}
          {amount !== null && item.days !== null && (
            <p className="text-xs font-bold text-navy-400">za {length(item.days)}</p>
          )}
        </div>
      </div>

      {item.kind === 'leave' && item.days !== null ? (
        <Window item={item} timeline={timeline} start={segment?.start ?? null} />
      ) : (
        <p className="mt-3 flex items-center gap-2 text-sm">
          <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-bold', urgent ? 'bg-sun-100 text-sun-700' : 'bg-navy-50 text-navy-700')}>
            {countdown}
          </span>
          <span className="font-bold text-navy-700">wniosek do {formatShortDate(item.last_day)}</span>
        </p>
      )}

      <p className="mt-3 text-sm leading-relaxed text-pretty text-navy-500">{item.text}</p>

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-4">
        {item.kind === 'choice' && item.id === 'left-rate-815' ? (
          <>
            {chose815 && (
              <span className="flex h-9 items-center gap-1.5 rounded-full bg-zus-50 px-3.5 text-sm font-bold text-zus-700">
                <Check className="size-4" /> Wybrane 81,5%
              </span>
            )}
            <Action
              primary={!chose815}
              icon={chose815 ? undefined : <Scale className="size-4" />}
              onClick={() =>
                void onApply(
                  { rate_815: !chose815 },
                  chose815 ? 'Zostajecie przy 100% i 70%' : 'Wybrano 81,5% przez cały urlop',
                  chose815 ? undefined : `Wniosek o 81,5% złóż najpóźniej ${formatShortDate(item.last_day)}.`,
                )
              }
            >
              {chose815 ? 'Wolę 100% i 70%' : 'Wybieram 81,5%'}
            </Action>
            {!chose815 && <Action onClick={onCompare}>Porównaj</Action>}
          </>
        ) : (
          request && (
            <Action primary icon={<FilePenLine className="size-4" />} onClick={() => onFill(request.id)}>
              Wypełnij wniosek
            </Action>
          )
        )}
        <Action
          icon={<CalendarPlus className="size-4" />}
          onClick={() => downloadCalendar(fileName(item.title), [calendarEvent(item)])}
        >
          Do kalendarza
        </Action>
      </div>
    </motion.li>
  )
}

function Action({
  primary = false,
  icon,
  onClick,
  children,
}: {
  primary?: boolean
  icon?: ReactNode
  onClick: () => void
  children: ReactNode
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileTap={{ scale: 0.96, transition: SPRING_PRESS }}
      className={cn(
        'flex h-9 items-center gap-1.5 rounded-full px-3.5 text-sm font-bold transition-[background-color,border-color,color] duration-150',
        'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-1 focus-visible:outline-none',
        primary
          ? 'bg-zus-600 text-white hover:bg-zus-700'
          : 'border border-line text-navy-700 hover:border-navy-200 hover:bg-navy-50',
      )}
    >
      {icon}
      {children}
    </motion.button>
  )
}

/**
 * The window the leave can still be taken in, to scale: from today (or the day it opens) to the
 * last day. The dark end is the latest the whole of it fits; its first day is the engine's
 * `start_by`.
 */
function Window({ item, timeline, start }: { item: Leftover; timeline: Timeline; start: string | null }) {
  const today = timeline.today
  const from = start && start > today ? start : today
  const total = dayNumber(item.last_day) - dayNumber(from) + 1
  const latest = item.start_by ? dayNumber(item.last_day) - dayNumber(item.start_by) + 1 : (item.days ?? 0)
  const share = total > 0 ? Math.min(1, Math.max(0.025, latest / total)) : 1
  return (
    <div className="mt-4">
      <div className="relative h-2.5 rounded-full bg-navy-50" role="img" aria-label={`Do wykorzystania od ${formatShortDate(from)} do ${formatShortDate(item.last_day)}`}>
        <motion.span
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.6, ease: EASE_OUT }}
          className="absolute inset-y-0 left-0 origin-left rounded-full bg-zus-100"
          style={{ right: `${share * 100}%` }}
        />
        <span
          className="absolute inset-y-0 right-0 rounded-full bg-sun-400"
          style={{ width: `${share * 100}%` }}
        />
        {from === today && <span className="absolute -top-1 left-0 h-[18px] w-0.5 rounded-full bg-navy-900" aria-hidden />}
      </div>
      <div className="mt-1.5 flex items-baseline justify-between gap-3 text-xs font-bold">
        <span className="text-navy-500">{from === today ? 'dziś' : `od ${formatShortDate(from)}`}</span>
        {item.start_by && (
          <span className="text-sun-700">zacznij najpóźniej {formatShortDate(item.start_by)}</span>
        )}
        <span className="text-navy-500">do {formatShortDate(item.last_day)}</span>
      </div>
    </div>
  )
}
