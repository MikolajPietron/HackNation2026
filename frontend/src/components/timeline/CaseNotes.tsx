import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  Baby,
  Calculator,
  CalendarClock,
  ChevronDown,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { TextStates } from '@/components/ui/text-states'
import type { ChangeSet } from '@/hooks/useAssistant'
import { EASE_OUT } from '@/lib/ease'
import { sourcesSummary } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { CaseNote } from '@/types'
import { Pulse } from './Pulse'

const KIND: Record<CaseNote['kind'], { icon: LucideIcon; tile: string }> = {
  situation: { icon: Baby, tile: 'bg-zus-600 text-white' },
  right: { icon: ShieldCheck, tile: 'bg-zus-100 text-zus-700' },
  risk: { icon: TriangleAlert, tile: 'bg-sun-400 text-navy-900' },
  choice: { icon: CalendarClock, tile: 'bg-zus-100 text-zus-700' },
  relief: { icon: Sparkles, tile: 'bg-sun-100 text-sun-700' },
  computed: { icon: Calculator, tile: 'bg-navy-100 text-navy-700' },
}

/**
 * "Twoja sytuacja": the calculator explains this family's case in plain words — which situation
 * it is, what they can choose or get and why, and what exactly the timeline shows. Points an
 * answer changed get the same ring as the changed elements of the timeline. The card starts
 * short (two lines per point, a risk in full) so the timeline stays in view; one button opens
 * the whole text and the sources.
 */
export function CaseNotes({ notes, changed }: { notes: CaseNote[]; changed: ChangeSet }) {
  const [open, setOpen] = useState(false)
  if (notes.length === 0) return null
  return (
    <section className="rounded-3xl bg-white p-5 shadow-card" aria-label="Twoja sytuacja">
      <h2 className="text-xs font-black tracking-widest text-zus-700 uppercase">Twoja sytuacja</h2>
      <ul id="case-notes" className="mt-3 grid gap-x-6 gap-y-4 @3xl:grid-cols-2">
        <AnimatePresence initial={false}>
          {notes.map((note) => {
            const { icon: Icon, tile } = KIND[note.kind]
            const sources = sourcesSummary(note.sources)
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
                <span
                  className={cn('relative grid size-9 shrink-0 place-items-center rounded-xl', tile)}
                >
                  <Icon className="size-4" />
                  {changed.notes.includes(note.id) && (
                    <Pulse key={changed.version} className="rounded-xl" />
                  )}
                </span>
                <div className="min-w-0">
                  <p className="leading-snug font-black text-navy-900">
                    <TextStates text={note.title} />
                  </p>
                  {/* What stands in the way of an entitlement is never cut short. */}
                  <p
                    className={cn(
                      'mt-0.5 text-[15px] leading-relaxed text-navy-700',
                      !open && note.kind !== 'risk' && 'line-clamp-2',
                    )}
                  >
                    {note.text}
                  </p>
                  {open && sources && (
                    <p className="mt-1 text-xs font-bold text-zus-700">{sources}</p>
                  )}
                </div>
              </motion.li>
            )
          })}
        </AnimatePresence>
      </ul>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="case-notes"
        className="mt-4 flex items-center gap-1 text-sm font-bold text-zus-700 underline-offset-2 hover:underline"
      >
        {open ? 'Zwiń wyjaśnienie' : 'Pokaż całe wyjaśnienie i źródła'}
        <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} />
      </button>
    </section>
  )
}
