// A section of the plan screen that holds a few tools under one heading, one at a time (the plan
// screen shows the answers first and the tools on demand: CLAUDE.md "Bez zagracenia"). The tabs
// are pills with an illustration, like the goals of "Plany dla Was"; the chosen tool comes in with
// a short fade. A tool keeps its own card and words.
import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ITEM } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import { useDragScroll } from '@/hooks/useDragScroll'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { cn } from '@/lib/utils'

export interface SectionTab {
  id: string
  label: string
  icon: string
  content: ReactNode
}

export function SectionTabs({ title, subtitle, tabs }: { title: string; subtitle: string; tabs: SectionTab[] }) {
  const [chosen, setChosen] = useState<string | null>(null)
  const row = useDragScroll<HTMLDivElement>()
  const id = useId()
  if (tabs.length === 0) return null
  const current = tabs.find((t) => t.id === chosen) ?? tabs[0]
  return (
    <motion.section variants={ITEM} aria-labelledby={`${id}-title`} className="mt-12 lg:mt-14">
      <h2 id={`${id}-title`} className="text-2xl leading-tight font-bold tracking-tight text-navy-900">
        {title}
      </h2>
      <p className="mt-1 text-navy-500">{subtitle}</p>
      {tabs.length > 1 && (
        <div
          ref={row}
          role="tablist"
          aria-label={title}
          className="scrollbar-none -mx-4 mt-4 flex gap-2 overflow-x-auto px-4 pb-1 lg:mx-0 lg:px-0"
        >
          {tabs.map((tab) => {
            const on = tab.id === current.id
            return (
              <motion.button
                key={tab.id}
                type="button"
                role="tab"
                id={`${id}-${tab.id}`}
                aria-selected={on}
                aria-controls={`${id}-panel`}
                onClick={() => setChosen(tab.id)}
                whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
                className={cn(
                  'flex h-12 shrink-0 items-center gap-2 rounded-full border pr-4 pl-1.5 text-sm font-bold whitespace-nowrap transition-[border-color,background-color,color] duration-150',
                  'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                  on ? 'border-zus-600 bg-zus-50 text-zus-900' : 'border-line text-navy-700 hover:border-navy-200',
                )}
              >
                <Illustration src={tab.icon} size="hint" />
                {tab.label}
              </motion.button>
            )
          })}
        </div>
      )}
      <div
        id={`${id}-panel`}
        role="tabpanel"
        aria-labelledby={tabs.length > 1 ? `${id}-${current.id}` : `${id}-title`}
        // The tools bring their own top margin from when they stood alone.
        className="mt-4 [&>*>*]:mt-0!"
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={current.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
            transition={{ duration: 0.22, ease: EASE_OUT }}
          >
            {current.content}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.section>
  )
}
