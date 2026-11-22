// Example families as cards (FUNKCJE F19): one click opens the plan of a ready, synthetic case,
// without AI and without the ZUS scans, so the demo works always. Used on the start screen and in
// "Przykładowe sprawy".
import { useState } from 'react'
import { motion } from 'motion/react'
import { LoaderCircle } from 'lucide-react'
import { loadCaseIntoPlan } from '@/api'
import { SimBadge } from '@/components/mocks/MockModal'
import { Illustration } from '@/components/ui/illustration'
import { todayIso } from '@/lib/dates'
import { SPRING_PRESS } from '@/lib/ease'
import { SAMPLES } from '@/lib/samples'
import type { Sample } from '@/lib/samples'
import { currentSessionId } from '@/lib/session'
import { cn } from '@/lib/utils'
import type { Scenario, SessionStart } from '@/types'

export function SampleFamilies({
  onLoaded,
  className,
}: {
  /** The example became the plan. */
  onLoaded: (start: SessionStart) => void
  className?: string
}) {
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const open = async (sample: Sample) => {
    if (loading) return
    setLoading(sample.id)
    setError(null)
    try {
      const facts = sample.facts(todayIso()) as Scenario
      onLoaded(await loadCaseIntoPlan(currentSessionId(), facts))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nie udało się otworzyć przykładu.')
    } finally {
      setLoading(null)
    }
  }

  return (
    <section className={className} aria-labelledby="sample-families">
      <div className="flex flex-wrap items-center gap-2">
        <h3 id="sample-families" className="font-bold text-navy-900">
          Przykładowe rodziny
        </h3>
        <SimBadge>dane przykładowe · bez AI</SimBadge>
      </div>
      <p className="mt-0.5 text-sm text-navy-500">Otwiera się od razu: cały plan policzony przez kalkulator.</p>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {SAMPLES.map((sample) => (
          <li key={sample.id}>
            <motion.button
              type="button"
              onClick={() => void open(sample)}
              disabled={loading !== null}
              whileTap={{ scale: 0.98, transition: SPRING_PRESS }}
              className={cn(
                'group flex h-full w-full items-center gap-3 rounded-2xl border border-line bg-white p-2.5 pr-3 text-left',
                'transition-[border-color,background-color,opacity] duration-150 hover:border-zus-300 hover:bg-zus-50/40',
                'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                loading !== null && loading !== sample.id && 'opacity-50',
              )}
            >
              <span className="transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:-translate-y-0.5">
                <Illustration src={sample.icon} size="event" className={sample.gentle ? 'bg-navy-50' : 'bg-zus-50'} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm leading-snug font-bold text-navy-900">{sample.title}</span>
                <span className="block text-xs leading-snug text-navy-500">{sample.shows}</span>
              </span>
              {loading === sample.id && <LoaderCircle className="size-4 shrink-0 animate-spin text-zus-600" />}
            </motion.button>
          </li>
        ))}
      </ul>
      {error && <p className="mt-3 rounded-2xl bg-alert-50 px-4 py-3 text-sm font-bold text-alert-600">{error}</p>}
    </section>
  )
}
