// "Co jeśli…" — events that change the plan (FUNKCJE F7, the brief's integrated calculator).
// An event the stress test models (twins, a premature birth, a job loss, the father taking over,
// "Za życiem") is shown on the real axis as a preview: the plan stays as it is until the parent
// says it happened (hooks/usePlanSpotlight, components/plan/ChangeBanner). The others tell the
// assistant, which recalculates the plan. A chip that is on takes the event back.
import { motion } from 'motion/react'
import { Eye, LoaderCircle } from 'lucide-react'
import { Illustration } from '@/components/ui/illustration'
import { useDragScroll } from '@/hooks/useDragScroll'
import { SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { cn } from '@/lib/utils'
import type { Scenario, StressEventId } from '@/types'

interface Event {
  id: string
  label: string
  icon: string
  /** Whether the event is part of the plan now. */
  on?: (scenario: Scenario) => boolean
  /** What the chip says to the assistant; `undo` takes it back. */
  prompt?: (scenario: Scenario | null) => string
  undo?: string
  /** Not computed yet: the chip only says so. */
  later?: string
  /** The stress test's events that show it on the axis, the first one available is used. */
  preview?: StressEventId[]
  /** Shown only when it can still happen. */
  show?: (scenario: Scenario | null) => boolean
}

const born = (scenario: Scenario | null) => scenario?.child_born === true

const EVENTS: Event[] = [
  {
    id: 'twins',
    label: 'Bliźnięta',
    icon: ICONS.blizniaki,
    preview: ['twins'],
    on: (s) => s.children_count === 2,
    prompt: (s) => (born(s) ? 'Urodziły się bliźnięta' : 'Spodziewamy się bliźniąt'),
    undo: 'Jednak jest jedno dziecko',
  },
  {
    id: 'triplets',
    label: 'Trojaczki',
    icon: ICONS.trojaczki,
    on: (s) => s.children_count === 3,
    prompt: (s) => (born(s) ? 'Urodziły się trojaczki' : 'Spodziewamy się trojaczków'),
    undo: 'Jednak jest jedno dziecko',
  },
  {
    // Supplementary leave is counted from a born child's hospital stay; before the birth the
    // assistant explains what would change.
    id: 'preterm',
    label: 'Wcześniak',
    icon: ICONS.inkubator,
    preview: ['premature'],
    on: (s) => s.hospital_care === true,
    prompt: (s) =>
      born(s)
        ? 'Dziecko urodziło się przedwcześnie i było w szpitalu'
        : 'Co się zmieni, jeśli dziecko urodzi się przedwcześnie?',
    undo: 'Dziecko urodziło się o czasie i nie było w szpitalu',
  },
  {
    id: 'hospital',
    label: 'Dziecko w szpitalu',
    icon: ICONS.szpital,
    on: (s) => s.hospital_care === true,
    prompt: (s) =>
      born(s)
        ? 'Dziecko zostało po porodzie dłużej w szpitalu'
        : 'Co się zmieni, jeśli dziecko zostanie po porodzie dłużej w szpitalu?',
    undo: 'Dziecko urodziło się o czasie i nie było w szpitalu',
  },
  {
    id: 'job',
    label: 'Utrata pracy w ciąży',
    icon: ICONS.karton,
    preview: ['job-loss-bankruptcy', 'job-loss-other'],
  },
  {
    id: 'father',
    label: 'Tata przejmuje urlop',
    icon: ICONS.tataZDzieckiem,
    preview: ['father-takeover'],
    on: (s) => s.father_takes_over === true,
    prompt: () => 'Tata przejmie urlop macierzyński po 14 tygodniach',
    undo: 'Tata jednak nie przejmie urlopu macierzyńskiego',
  },
  {
    id: 'life',
    label: '„Za życiem”',
    icon: ICONS.serce,
    preview: ['za-zyciem'],
    on: (s) => s.za_zyciem === true,
    prompt: () => 'Dziecko ma zaświadczenie „Za życiem”',
    undo: 'Dziecko nie ma zaświadczenia „Za życiem”',
  },
]

export function WhatIf({
  scenario,
  busy,
  onSend,
  onMock,
  available,
  previewing,
  loading,
  onPreview,
}: {
  scenario: Scenario | null
  busy: boolean
  onSend: (text: string) => void
  onMock: (message: string) => void
  /** Events of the stress test that can still happen to this family; null while loading. */
  available: Set<StressEventId> | null
  /** The event shown on the axis now, and the one being counted. */
  previewing: StressEventId | null
  loading: StressEventId | null
  /** Show an event on the axis. */
  onPreview: (id: StressEventId) => void
}) {
  const row = useDragScroll<HTMLDivElement>()
  return (
    <div
      ref={row}
      className="scrollbar-none -mx-1 flex cursor-grab items-center gap-2 overflow-x-auto px-1 py-1 pr-12 select-none data-[dragging]:cursor-grabbing [mask-image:linear-gradient(to_right,#000_calc(100%-56px),transparent)]"
    >
      <span className="mr-1 shrink-0 text-sm font-bold text-navy-500">Co jeśli…</span>
      {EVENTS.filter((event) => !event.show || event.show(scenario)).map((event) => {
        const active = scenario !== null && event.on !== undefined && event.on(scenario)
        const stress = event.preview?.find((id) => available?.has(id)) ?? null
        // A preview-only event (no chat prompt) is shown once the stress test knows it can happen.
        if (!event.prompt && !stress) return null
        const shown =
          stress !== null &&
          (previewing === stress || Boolean(previewing?.startsWith('job-loss-') && stress.startsWith('job-loss-')))
        const counting = stress !== null && loading === stress
        return (
          <motion.button
            key={event.id}
            type="button"
            aria-pressed={active || shown}
            disabled={(busy && event.prompt !== undefined && !stress) || loading !== null}
            title={stress && !active ? 'Pokaż na osi, bez zmiany planu' : undefined}
            onClick={() => {
              if (active && event.undo) onSend(event.undo)
              else if (stress) onPreview(stress)
              else if (event.later) onMock(`${event.later} — policzy to kolejna faza silnika.`)
              else if (event.prompt) onSend(event.prompt(scenario))
            }}
            whileTap={{ scale: 0.96, transition: SPRING_PRESS }}
            className={cn(
              'flex h-10 shrink-0 items-center gap-2 rounded-full border pr-4 pl-2.5 text-sm font-bold whitespace-nowrap transition-[border-color,background-color,color,opacity] duration-200',
              'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none disabled:opacity-50',
              active
                ? 'border-zus-600 bg-zus-600 text-white'
                : shown
                  ? 'border-dashed border-sun-400 bg-sun-100 text-navy-900'
                  : event.later
                    ? 'border-dashed border-navy-200 text-navy-500 hover:border-navy-300 hover:text-navy-700'
                    : 'border-line text-navy-900 hover:border-zus-300 hover:bg-zus-50',
            )}
          >
            {counting ? (
              <LoaderCircle className="size-6 animate-spin p-0.5 text-navy-400" />
            ) : (
              <Illustration src={event.icon} size="hint" />
            )}
            {event.label}
            {shown && <Eye className="size-4 text-sun-700" />}
          </motion.button>
        )
      })}
    </div>
  )
}
