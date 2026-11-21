// Inline calendar for the onboarding date step. No popover: on a full-screen step the month grid
// is the content. Motion from Spectrum UI's tokens (lib/ease.ts): months slide with a blur, the
// selected-day pill glides between days, the header label swaps with TextStates.
//
// Dates are ISO strings computed in UTC, like the rest of the frontend (lib/dates.ts).
import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import type { Variants } from 'motion/react'
import { ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { TextStates } from '@/components/ui/text-states'
import { addDaysIso } from '@/lib/dates'
import { EASE_OUT, SPRING_LAYOUT } from '@/lib/ease'
import { cn } from '@/lib/utils'

interface Month {
  year: number
  /** 0–11 */
  month: number
}

const WEEKDAYS = ['pn', 'wt', 'śr', 'cz', 'pt', 'so', 'nd']
const monthLong = new Intl.DateTimeFormat('pl-PL', { month: 'long', timeZone: 'UTC' })
const monthShort = new Intl.DateTimeFormat('pl-PL', { month: 'short', timeZone: 'UTC' })
const dayLabel = new Intl.DateTimeFormat('pl-PL', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})

const toIso = (year: number, month: number, day: number) =>
  new Date(Date.UTC(year, month, day)).toISOString().slice(0, 10)
const utc = (iso: string) => new Date(`${iso}T00:00:00Z`)
const monthOf = (iso: string): Month => {
  const date = utc(iso)
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() }
}
const shift = (m: Month, months: number): Month => {
  const date = new Date(Date.UTC(m.year, m.month + months, 1))
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() }
}
const key = (m: Month) => m.year * 12 + m.month
const daysIn = (m: Month) => new Date(Date.UTC(m.year, m.month + 1, 0)).getUTCDate()
/** 0 = Monday. */
const weekday = (iso: string) => (utc(iso).getUTCDay() + 6) % 7
const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** Always 6 weeks, so the grid keeps its height from month to month. */
function cells(m: Month): (string | null)[] {
  const lead = weekday(toIso(m.year, m.month, 1))
  const days = daysIn(m)
  return Array.from({ length: 42 }, (_, index) => {
    const day = index - lead + 1
    return day >= 1 && day <= days ? toIso(m.year, m.month, day) : null
  })
}

const SLIDE: Variants = {
  from: (direction: number) => ({ x: direction * 36, opacity: 0, filter: 'blur(4px)' }),
  in: { x: 0, opacity: 1, filter: 'blur(0px)' },
  out: (direction: number) => ({ x: direction * -36, opacity: 0, filter: 'blur(4px)' }),
}

interface Props {
  value: string
  min: string
  max: string
  today: string
  label: string
  onChange: (value: string) => void
}

export function Calendar({ value, min, max, today, label, onChange }: Props) {
  const clamp = (iso: string) => (iso < min ? min : iso > max ? max : iso)
  const [view, setView] = useState<Month>(() => monthOf(value || clamp(today)))
  const [mode, setMode] = useState<'days' | 'months'>('days')
  const [direction, setDirection] = useState(1)
  const [focus, setFocus] = useState(() => value || clamp(today))
  const grid = useRef<HTMLDivElement>(null)
  const moveFocus = useRef(false)

  const first = monthOf(min)
  const last = monthOf(max)
  const minKey = key(first)
  const maxKey = key(last)
  // Days view pages by month, months view by year.
  const step = mode === 'days' ? 1 : 12
  const canPrev = mode === 'days' ? key(view) > minKey : view.year > first.year
  const canNext = mode === 'days' ? key(view) < maxKey : view.year < last.year

  const goTo = (next: Month) => {
    setDirection(key(next) >= key(view) ? 1 : -1)
    setView(next)
  }
  const toggleMode = () => {
    if (mode === 'months') {
      // Paging by year can land on a month outside the range.
      setView((v) => (key(v) < minKey ? first : key(v) > maxKey ? last : v))
      setMode('days')
    } else setMode('months')
  }

  // Keyboard moves focus between days, also into the next month once it has rendered.
  useEffect(() => {
    if (!moveFocus.current) return
    moveFocus.current = false
    grid.current?.querySelector<HTMLButtonElement>(`[data-day="${focus}"]`)?.focus()
  }, [focus, view])

  const days = cells(view)
  const inView = (iso: string) => key(monthOf(iso)) === key(view)
  const enabled = (iso: string) => iso >= min && iso <= max
  const tabbable = inView(focus) && enabled(focus) ? focus : days.find((d) => d && enabled(d))

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }
    const from = tabbable ?? focus
    let next: string | null = null
    if (event.key in moves) next = addDaysIso(from, moves[event.key])
    else if (event.key === 'Home') next = addDaysIso(from, -weekday(from))
    else if (event.key === 'End') next = addDaysIso(from, 6 - weekday(from))
    else if (event.key === 'PageUp' || event.key === 'PageDown') {
      const target = shift(monthOf(from), event.key === 'PageUp' ? -1 : 1)
      next = toIso(target.year, target.month, Math.min(utc(from).getUTCDate(), daysIn(target)))
    }
    if (!next) return
    event.preventDefault()
    next = clamp(next)
    moveFocus.current = true
    setFocus(next)
    if (!inView(next)) goTo(monthOf(next))
  }

  return (
    <div className="mx-auto w-full max-w-100 rounded-4xl border border-line bg-white p-3 sm:p-5 lg:max-w-md">
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          onClick={toggleMode}
          aria-expanded={mode === 'months'}
          className="flex h-11 items-center gap-1.5 rounded-full px-3 text-lg font-bold text-navy-900 transition-colors hover:bg-navy-50 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
        >
          <TextStates
            text={
              mode === 'days'
                ? `${capitalize(monthLong.format(utc(toIso(view.year, view.month, 1))))} ${view.year}`
                : String(view.year)
            }
          />
          <ChevronDown
            className={cn(
              'size-4 text-navy-500 transition-transform duration-300',
              mode === 'months' && 'rotate-180',
            )}
          />
        </button>
        <div className="flex gap-1">
          <NavButton label="Wcześniej" disabled={!canPrev} onClick={() => goTo(shift(view, -step))}>
            <ChevronLeft className="size-5" />
          </NavButton>
          <NavButton label="Później" disabled={!canNext} onClick={() => goTo(shift(view, step))}>
            <ChevronRight className="size-5" />
          </NavButton>
        </div>
      </div>

      <div className="relative h-80 overflow-hidden sm:h-86 lg:h-98">
        <AnimatePresence mode="popLayout" initial={false} custom={direction}>
          {mode === 'days' ? (
            <motion.div
              key={`days-${key(view)}`}
              custom={direction}
              variants={SLIDE}
              initial="from"
              animate="in"
              exit="out"
              transition={{ duration: 0.35, ease: EASE_OUT }}
            >
              <div className="grid grid-cols-7 justify-items-center pb-1 text-xs font-bold text-navy-400 uppercase">
                {WEEKDAYS.map((day) => (
                  <span key={day} className="grid h-8 place-items-center">
                    {day}
                  </span>
                ))}
              </div>
              <div
                ref={grid}
                role="group"
                aria-label={label}
                onKeyDown={onKeyDown}
                className="grid grid-cols-7 justify-items-center gap-y-1"
              >
                {days.map((day, index) =>
                  day ? (
                    <Day
                      key={day}
                      iso={day}
                      selected={day === value}
                      today={day === today}
                      disabled={!enabled(day)}
                      tabbable={day === tabbable}
                      layoutGroup={key(view)}
                      onSelect={() => {
                        setFocus(day)
                        onChange(day)
                      }}
                    />
                  ) : (
                    <span key={`empty-${index}`} className="size-11 sm:size-12 lg:size-14" />
                  ),
                )}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key={`months-${view.year}`}
              custom={direction}
              variants={SLIDE}
              initial="from"
              animate="in"
              exit="out"
              transition={{ duration: 0.35, ease: EASE_OUT }}
              className="grid h-full grid-cols-3 content-center gap-2"
            >
              {Array.from({ length: 12 }, (_, month) => {
                const m = { year: view.year, month }
                const out = key(m) < minKey || key(m) > maxKey
                const chosen = value !== '' && key(monthOf(value)) === key(m)
                return (
                  <button
                    key={month}
                    type="button"
                    disabled={out}
                    onClick={() => {
                      goTo(m)
                      setMode('days')
                    }}
                    className={cn(
                      'h-16 rounded-2xl text-base font-bold capitalize transition-[background-color,color,transform] duration-150 active:scale-[0.96]',
                      'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                      chosen
                        ? 'bg-zus-600 text-white'
                        : out
                          ? 'text-navy-200'
                          : 'text-navy-900 hover:bg-navy-50',
                      key(m) === key(monthOf(today)) && !chosen && 'ring-1 ring-line ring-inset',
                    )}
                  >
                    {monthShort.format(utc(toIso(view.year, month, 1))).replace('.', '')}
                  </button>
                )
              })}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

function Day({
  iso,
  selected,
  today,
  disabled,
  tabbable,
  layoutGroup,
  onSelect,
}: {
  iso: string
  selected: boolean
  today: boolean
  disabled: boolean
  tabbable: boolean
  layoutGroup: number
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      data-day={iso}
      disabled={disabled}
      tabIndex={tabbable ? 0 : -1}
      aria-pressed={selected}
      aria-current={today ? 'date' : undefined}
      aria-label={dayLabel.format(utc(iso))}
      onClick={onSelect}
      className={cn(
        'relative grid size-11 place-items-center rounded-full text-base font-bold tabular-nums sm:size-12 lg:size-14 lg:text-lg',
        'transition-[color,background-color,transform] duration-150 active:scale-[0.92]',
        'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        selected
          ? 'text-white'
          : disabled
            ? 'cursor-default text-navy-200'
            : 'text-navy-900 hover:bg-navy-50',
      )}
    >
      {selected && (
        <motion.span
          layoutId={`calendar-day-${layoutGroup}`}
          transition={SPRING_LAYOUT}
          className="absolute inset-0 rounded-full bg-zus-600"
        />
      )}
      <span className="relative">{utc(iso).getUTCDate()}</span>
      {today && (
        <span
          className={cn(
            'absolute bottom-1.5 left-1/2 size-1 -translate-x-1/2 rounded-full',
            selected ? 'bg-white' : 'bg-zus-600',
          )}
        />
      )}
    </button>
  )
}

function NavButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string
  disabled: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="grid size-11 place-items-center rounded-full text-navy-700 transition-[background-color,opacity,transform] duration-150 hover:bg-navy-50 active:scale-[0.92] disabled:pointer-events-none disabled:opacity-25 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
    >
      {children}
    </button>
  )
}
