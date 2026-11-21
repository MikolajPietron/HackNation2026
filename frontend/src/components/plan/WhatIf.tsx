// "Co jeśli…" — events that change the plan (FUNKCJE F7, the brief's integrated calculator).
// Twins and triplets already work: the chip answers the assistant, the engine recalculates and the
// old plan fades out as a shadow. The other events wait for the engine and say so.
import { motion } from 'motion/react'
import { Illustration } from '@/components/ui/illustration'
import { useDragScroll } from '@/hooks/useDragScroll'
import { SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { cn } from '@/lib/utils'
import type { Scenario } from '@/types'

interface Event {
  id: string
  label: string
  icon: string
  /** Children count this event sets; events without it are not computed yet. */
  children?: number
  prompt?: string
  later?: string
}

const EVENTS: Event[] = [
  { id: 'twins', label: 'Bliźnięta', icon: ICONS.blizniaki, children: 2, prompt: 'Spodziewamy się bliźniąt' },
  { id: 'triplets', label: 'Trojaczki', icon: ICONS.trojaczki, children: 3, prompt: 'Spodziewamy się trojaczków' },
  { id: 'preterm', label: 'Wcześniak', icon: ICONS.inkubator, later: 'Wcześniak i urlop uzupełniający' },
  { id: 'hospital', label: 'Dziecko w szpitalu', icon: ICONS.szpital, later: 'Pobyt dziecka w szpitalu' },
  { id: 'job', label: 'Utrata pracy w ciąży', icon: ICONS.karton, later: 'Utrata pracy w ciąży' },
  { id: 'father', label: 'Tata przejmuje urlop', icon: ICONS.tataZDzieckiem, later: 'Przejęcie urlopu przez tatę' },
  { id: 'life', label: '„Za życiem”', icon: ICONS.serce, later: 'Dłuższy rodzicielski „Za życiem”' },
]

export function WhatIf({
  scenario,
  busy,
  onSend,
  onMock,
}: {
  scenario: Scenario | null
  busy: boolean
  onSend: (text: string) => void
  onMock: (message: string) => void
}) {
  const count = scenario?.children_count ?? 1
  const row = useDragScroll<HTMLDivElement>()
  return (
    <div
      ref={row}
      className="scrollbar-none -mx-1 flex cursor-grab items-center gap-2 overflow-x-auto px-1 py-1 pr-12 select-none data-[dragging]:cursor-grabbing [mask-image:linear-gradient(to_right,#000_calc(100%-56px),transparent)]"
    >
      <span className="mr-1 shrink-0 text-sm font-bold text-navy-500">Co jeśli…</span>
      {EVENTS.map((event) => {
        const active = event.children !== undefined && count === event.children
        return (
          <motion.button
            key={event.id}
            type="button"
            aria-pressed={active}
            disabled={busy && event.prompt !== undefined}
            onClick={() => {
              if (event.later) onMock(`${event.later} — policzy to kolejna faza silnika.`)
              else if (active) onSend('Jednak spodziewamy się jednego dziecka')
              else if (event.prompt) onSend(event.prompt)
            }}
            whileTap={{ scale: 0.96, transition: SPRING_PRESS }}
            className={cn(
              'flex h-10 shrink-0 items-center gap-2 rounded-full border pr-4 pl-2.5 text-sm font-bold whitespace-nowrap transition-[border-color,background-color,color,opacity] duration-200',
              'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none disabled:opacity-50',
              active
                ? 'border-zus-600 bg-zus-600 text-white'
                : event.later
                  ? 'border-dashed border-navy-200 text-navy-500 hover:border-navy-300 hover:text-navy-700'
                  : 'border-line text-navy-900 hover:border-zus-300 hover:bg-zus-50',
            )}
          >
            <Illustration src={event.icon} size="hint" />
            {event.label}
          </motion.button>
        )
      })}
    </div>
  )
}
