// "Dlaczego tak?": the whole case explanation, in the engine's order (the situation, the rights,
// what can be chosen, what we computed; CLAUDE.md "Wyjaśnianie przypadku"), each point with its
// sources, then the calculator's assumptions. Opened from a tile it starts at that tile's point.
import { useEffect, useRef } from 'react'
import { Emphasis } from '@/components/ui/emphasis'
import { sourcesSummary } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { CaseNote, Timeline } from '@/types'

const KIND: Record<CaseNote['kind'], { label: string; className: string }> = {
  situation: { label: 'Sytuacja', className: 'bg-zus-600 text-white' },
  right: { label: 'Prawo', className: 'bg-zus-50 text-zus-700' },
  risk: { label: 'Uwaga', className: 'bg-sun-400 text-navy-900' },
  choice: { label: 'Do wyboru', className: 'bg-zus-50 text-zus-700' },
  relief: { label: 'Ułatwienie', className: 'bg-sun-100 text-sun-700' },
  computed: { label: 'Co policzyliśmy', className: 'bg-navy-50 text-navy-700' },
}

export function Explanation({ timeline, focusId }: { timeline: Timeline; focusId?: string }) {
  const focused = useRef<HTMLLIElement>(null)
  useEffect(() => {
    focused.current?.scrollIntoView({ block: 'center' })
  }, [focusId])

  return (
    <div className="space-y-6 text-navy-700">
      <header className="pr-10">
        <h2 className="text-2xl font-bold tracking-tight text-navy-900">Dlaczego tak?</h2>
        <p className="mt-2">
          Daty liczy kalkulator reguł, bez AI. Każdy punkt ma dosłowny cytat z Przewodnika ZUS
          albo Kodeksu pracy.
        </p>
      </header>
      {timeline.notes.length > 0 && (
        <ol className="space-y-2">
          {timeline.notes.map((note) => {
            const sources = sourcesSummary(note.sources)
            const kind = KIND[note.kind]
            return (
              <li
                key={note.id}
                ref={note.id === focusId ? focused : undefined}
                className={cn(
                  'rounded-2xl px-4 py-3 transition-colors duration-300',
                  note.id === focusId && 'bg-sun-100/60',
                )}
              >
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-bold', kind.className)}>
                  {kind.label}
                </span>
                <p className="mt-1.5 font-bold text-navy-900">{note.title}</p>
                <p className="mt-0.5 leading-relaxed">
                  <Emphasis text={note.text} className="text-navy-900" />
                </p>
                {sources && <p className="mt-1 text-sm font-bold text-zus-700">{sources}</p>}
              </li>
            )
          })}
        </ol>
      )}
      {timeline.assumptions.length > 0 && (
        <section>
          <h3 className="font-bold text-navy-900">Założenia kalkulatora</h3>
          <ul className="mt-2 space-y-1.5">
            {timeline.assumptions.map((text) => (
              <li key={text} className="flex gap-3">
                <span className="mt-[0.6em] size-1.5 shrink-0 rounded-full bg-navy-200" />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
