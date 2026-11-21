import { AnimatePresence, motion } from 'motion/react'
import { Baby, Calculator, CalendarClock, Sparkles } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { TextStates } from '@/components/ui/text-states'
import { EASE_OUT } from '@/lib/ease'
import { sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { CaseNote } from '@/types'

const KIND: Record<CaseNote['kind'], { icon: LucideIcon; tile: string }> = {
  situation: { icon: Baby, tile: 'bg-zus-600 text-white' },
  choice: { icon: CalendarClock, tile: 'bg-zus-100 text-zus-700' },
  relief: { icon: Sparkles, tile: 'bg-sun-100 text-sun-700' },
  computed: { icon: Calculator, tile: 'bg-navy-100 text-navy-700' },
}

/**
 * "Twoja sytuacja": the calculator explains this family's case in plain words — which situation
 * it is, what they can choose or get and why, and what exactly the timeline shows.
 */
export function CaseNotes({ notes }: { notes: CaseNote[] }) {
  if (notes.length === 0) return null
  return (
    <section className="rounded-3xl bg-white p-5 shadow-card" aria-label="Twoja sytuacja">
      <h2 className="text-xs font-black tracking-widest text-zus-700 uppercase">Twoja sytuacja</h2>
      <ul className="mt-3 grid gap-x-6 gap-y-4 @3xl:grid-cols-2">
        <AnimatePresence initial={false}>
          {notes.map((note) => {
            const { icon: Icon, tile } = KIND[note.kind]
            const labels = [...new Set(note.sources.map(sourceLabel))]
            return (
              <motion.li
                key={note.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, ease: EASE_OUT }}
                className="flex gap-3"
              >
                <span className={cn('grid size-9 shrink-0 place-items-center rounded-xl', tile)}>
                  <Icon className="size-4" />
                </span>
                <div className="min-w-0">
                  <p className="leading-snug font-black text-navy-900">
                    <TextStates text={note.title} />
                  </p>
                  <p className="mt-0.5 text-[15px] leading-relaxed text-navy-700">{note.text}</p>
                  {labels.length > 0 && (
                    <p className="mt-1 text-xs font-bold text-zus-700">{labels.join(' · ')}</p>
                  )}
                </div>
              </motion.li>
            )
          })}
        </AnimatePresence>
      </ul>
    </section>
  )
}
