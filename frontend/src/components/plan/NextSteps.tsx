// "Co przed Wami": what lies ahead, month by month. The whole section folds away, and so does
// every month; months start folded, each showing how many steps it holds, their pictures and
// the first of them, so the list reads at a glance and opens where the parent wants to look.
// All the steps go into the parent's own calendar with one click (an .ics file, lib/ics.ts).
// One line per step: a calendar page with the date, what it is, and how long until it; what is
// still to decide carries a tag. No descriptions: the details (with the source) open on a click,
// and a hover lights the element up on the axis. A month with a changed step is ringed in amber.
import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { CalendarPlus, ChevronRight, Lock } from 'lucide-react'
import { Pulse } from '@/components/timeline/Pulse'
import { AccordionItem } from '@/components/ui/accordion'
import { Illustration } from '@/components/ui/illustration'
import { isoFromDay } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { downloadCalendar, planEvents } from '@/lib/ics'
import { nextSteps } from '@/lib/plan'
import type { Step } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { Timeline } from '@/types'

const monthShort = new Intl.DateTimeFormat('pl-PL', { month: 'short', timeZone: 'UTC' })
const monthLong = new Intl.DateTimeFormat('pl-PL', { month: 'long', year: 'numeric', timeZone: 'UTC' })

const OPEN_KEY = 'next-steps-open'

/** 1 krok, 2 kroki, 5 kroków (and the like for any noun). */
function plural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return `${n} ${one}`
  const last = n % 10
  const lastTwo = n % 100
  return `${n} ${last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? few : many}`
}

interface Month {
  key: string
  title: string
  steps: Step[]
}

/** The steps ahead in date order, cut into calendar months. */
function byMonth(timeline: Timeline): Month[] {
  const groups = nextSteps(timeline)
  const months: Month[] = []
  for (const step of [...groups.now, ...groups.soon, ...groups.later]) {
    const iso = isoFromDay(step.day)
    const key = iso.slice(0, 7)
    let month = months.at(-1)
    if (!month || month.key !== key) {
      month = { key, title: monthLong.format(new Date(`${key}-01T00:00:00Z`)), steps: [] }
      months.push(month)
    }
    month.steps.push(step)
  }
  return months
}

/** Whether the section is open, remembered on this device (storage may be blocked). */
function useStoredOpen(): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(() => {
    try {
      return window.localStorage.getItem(OPEN_KEY) !== 'closed'
    } catch {
      return true
    }
  })
  const choose = (next: boolean) => {
    setOpen(next)
    try {
      window.localStorage.setItem(OPEN_KEY, next ? 'open' : 'closed')
    } catch {
      // Not remembered; the toggle still works.
    }
  }
  return [open, choose]
}

export function NextSteps({
  timeline,
  changedIds,
  changeVersion,
  hoveredId,
  onHover,
  onSelect,
}: {
  timeline: Timeline
  changedIds: Set<string>
  changeVersion: number
  hoveredId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}) {
  const months = useMemo(() => byMonth(timeline), [timeline])
  const [open, setOpen] = useStoredOpen()
  const [openMonths, setOpenMonths] = useState<Set<string>>(() => new Set())
  const year = timeline.today.slice(0, 4)
  const thisMonth = timeline.today.slice(0, 7)
  if (months.length === 0) return null

  const count = months.reduce((sum, m) => sum + m.steps.length, 0)
  const allOpen = months.every((m) => openMonths.has(m.key))
  const toggleMonth = (key: string) =>
    setOpenMonths((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  return (
    <section aria-labelledby="next-steps" className="mt-6">
      <div className="flex items-center gap-1 sm:gap-2">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-controls="next-steps-months"
          className="group -ml-2 flex min-w-0 flex-1 items-center gap-2 rounded-2xl px-2 py-1.5 text-left transition-colors hover:bg-navy-50/60 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
        >
          <span className="flex min-w-0 flex-col sm:flex-row sm:items-baseline sm:gap-2">
            <h3 id="next-steps" className="text-lg font-bold whitespace-nowrap text-navy-900">
              Co przed Wami
            </h3>
            <span className="text-sm font-bold whitespace-nowrap text-navy-400">
              {plural(count, 'krok', 'kroki', 'kroków')} · {plural(months.length, 'miesiąc', 'miesiące', 'miesięcy')}
            </span>
          </span>
          <ChevronRight
            className={cn(
              'ml-auto size-5 shrink-0 text-navy-400 transition-transform duration-200 group-hover:text-navy-700',
              open && 'rotate-90',
            )}
          />
        </button>
        <button
          type="button"
          onClick={() => downloadCalendar('plan-urlopow', planEvents(timeline))}
          aria-label="Dodaj terminy do kalendarza"
          title="Pobierz plik z terminami do kalendarza w telefonie albo komputerze (przypomnienie tydzień wcześniej)"
          className="flex h-9 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-sm font-bold text-navy-500 transition-colors hover:bg-navy-50 hover:text-navy-900 sm:px-3"
        >
          <CalendarPlus className="size-4" />
          <span className="hidden sm:inline">Do kalendarza</span>
        </button>
        {open && months.length > 1 && (
          <button
            type="button"
            onClick={() => setOpenMonths(allOpen ? new Set() : new Set(months.map((m) => m.key)))}
            className="h-9 shrink-0 rounded-full px-2.5 text-sm font-bold text-zus-700 transition-colors hover:bg-zus-50 sm:px-3"
          >
            {allOpen ? 'Zwiń' : 'Rozwiń'}
            <span className="hidden sm:inline">{allOpen ? ' miesiące' : ' wszystkie'}</span>
          </button>
        )}
      </div>

      {open && (
        <motion.div
          id="next-steps-months"
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: EASE_OUT }}
          className="mt-3 space-y-2"
        >
          {months.map((month) => (
            <MonthItem
              key={month.key}
              month={month}
              current={month.key === thisMonth}
              open={openMonths.has(month.key)}
              onToggle={() => toggleMonth(month.key)}
              year={year}
              changedIds={changedIds}
              changeVersion={changeVersion}
              hoveredId={hoveredId}
              onHover={onHover}
              onSelect={onSelect}
            />
          ))}
        </motion.div>
      )}
    </section>
  )
}

function MonthItem({
  month,
  current,
  open,
  onToggle,
  year,
  changedIds,
  changeVersion,
  hoveredId,
  onHover,
  onSelect,
}: {
  month: Month
  current: boolean
  open: boolean
  onToggle: () => void
  year: string
  changedIds: Set<string>
  changeVersion: number
  hoveredId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}) {
  const decide = month.steps.filter((s) => s.decide).length
  const overdue = month.steps.filter((s) => s.overdue).length
  const noReturn = month.steps.some((s) => s.noReturn)
  const changed = month.steps.some((s) => changedIds.has(s.id))
  const icons = [...new Set(month.steps.map((s) => s.icon))].slice(0, 4)
  const lit = !open && month.steps.some((s) => s.id === hoveredId)

  return (
    <AccordionItem
      open={open}
      onToggle={onToggle}
      highlight={changed && !open}
      className={cn(lit && 'border-navy-200 bg-navy-50/40')}
      title={
        <span className="flex items-center gap-3 sm:gap-4">
          <span className="flex w-24 shrink-0 flex-col sm:w-32">
            <span className="font-bold text-navy-900 first-letter:uppercase">{month.title.replace(/ \d{4}$/, '')}</span>
            <span className="text-xs font-bold text-navy-400">
              {month.key.slice(0, 4)}
              {current && <span className="ml-1.5 text-zus-700">· teraz</span>}
            </span>
          </span>
          <span className="hidden shrink-0 -space-x-1.5 sm:flex" aria-hidden>
            {icons.map((icon) => (
              <span key={icon} className="grid size-8 place-items-center rounded-full bg-white ring-2 ring-white">
                <Illustration src={icon} size="hint" />
              </span>
            ))}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-bold text-navy-700">{plural(month.steps.length, 'krok', 'kroki', 'kroków')}</span>
            {!open && (
              <span className="block truncate text-sm text-navy-500">
                {month.steps.map((s) => s.title).join(' · ')}
              </span>
            )}
          </span>
        </span>
      }
      aside={
        <span className="hidden shrink-0 items-center gap-1.5 sm:flex">
          {overdue > 0 && (
            <span className="rounded-full bg-alert-50 px-2 py-0.5 text-[11px] font-bold text-alert-600">
              {overdue} po terminie
            </span>
          )}
          {decide > 0 && (
            <span className="rounded-full bg-zus-50 px-2 py-0.5 text-[11px] font-bold text-zus-700">
              {decide} do wyboru
            </span>
          )}
          {noReturn && (
            <span className="grid size-6 place-items-center rounded-full bg-sun-100 text-sun-700" title="Punkt bez powrotu">
              <Lock className="size-3" strokeWidth={2.5} />
            </span>
          )}
        </span>
      }
    >
      <ul className="divide-y divide-line px-2 pb-2 sm:px-3">
        {month.steps.map((step, index) => (
          <Row
            key={step.key}
            step={step}
            index={index}
            showYear={step.date.slice(0, 4) !== year}
            changed={changedIds.has(step.id)}
            changeVersion={changeVersion}
            active={hoveredId === step.id}
            onHover={onHover}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </AccordionItem>
  )
}

function Row({
  step,
  index,
  showYear,
  changed,
  changeVersion,
  active,
  onHover,
  onSelect,
}: {
  step: Step
  index: number
  showYear: boolean
  changed: boolean
  changeVersion: number
  active: boolean
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}) {
  const date = new Date(`${step.date}T00:00:00Z`)
  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.04, ease: EASE_OUT }}
    >
      <button
        type="button"
        onClick={() => onSelect(step.id)}
        onMouseEnter={() => onHover(step.id)}
        onMouseLeave={() => onHover(null)}
        className={cn(
          'group flex w-full items-center gap-3 rounded-2xl px-2 py-2.5 text-left transition-colors duration-150 sm:gap-4',
          'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
          active ? 'bg-navy-50' : 'hover:bg-navy-50/60',
        )}
      >
        {/* A page from a wall calendar. */}
        <span
          className={cn(
            'relative grid w-12 shrink-0 overflow-hidden rounded-xl border bg-white text-center leading-none',
            step.overdue ? 'border-alert-600/40' : 'border-line',
          )}
        >
          <span
            className={cn(
              'py-1 text-[10px] font-black tracking-wide uppercase',
              step.overdue ? 'bg-alert-50 text-alert-600' : step.decide ? 'bg-zus-50 text-zus-700' : 'bg-navy-50 text-navy-500',
            )}
          >
            {monthShort.format(date).replace('.', '')}
          </span>
          <span className="pt-1 text-lg font-bold text-navy-900">{date.getUTCDate()}</span>
          <span className="pb-1 text-[10px] font-bold text-navy-400">{showYear ? step.date.slice(0, 4) : ' '}</span>
          {changed && <Pulse key={changeVersion} className="rounded-xl" />}
        </span>
        <Illustration src={step.icon} size="hint" />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="font-bold text-navy-900">{step.title}</span>
            {step.decide && (
              <span className="rounded-full bg-zus-50 px-2 py-0.5 text-[11px] font-bold text-zus-700">do wyboru</span>
            )}
            {step.noReturn && <NoReturnTag />}
          </span>
          <span className={cn('block text-sm', step.overdue ? 'font-bold text-alert-600' : 'text-navy-500')}>
            {step.detail}
          </span>
        </span>
        <ChevronRight className="size-4 shrink-0 text-navy-300 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-navy-500" />
      </button>
    </motion.li>
  )
}

/** After this day the right is gone for good (FUNKCJE F10). */
export function NoReturnTag() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-sun-100 px-2 py-0.5 text-[11px] font-bold text-sun-700">
      <Lock className="size-3" strokeWidth={2.5} />
      bez powrotu
    </span>
  )
}
