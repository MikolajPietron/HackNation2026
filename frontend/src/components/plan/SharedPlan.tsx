// A plan shared by the other parent (`/plan/<token>`): read only, no chat, no changes, no personal
// data. The timeline, the money by month and the deadlines, and the plan as one A4 page.
import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence } from 'motion/react'
import { Eye, LoaderCircle, Printer } from 'lucide-react'
import { fetchShared } from '@/api'
import { Brand } from '@/components/layout/Brand'
import { Dialog } from '@/components/plan/Dialog'
import { MobileTimeline } from '@/components/plan/MobileTimeline'
import { TimelineCard } from '@/components/plan/TimelineCard'
import { ElementDetails } from '@/components/timeline/ElementDetails'
import { timelineItems } from '@/components/timeline/items'
import { Sheet } from '@/components/ui/sheet'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { formatShortDate } from '@/lib/dates'
import { formatPln } from '@/lib/money'
import type { Scenario, Timeline } from '@/types'

const NO_CHANGES = new Set<string>()

export function SharedPlan({ token }: { token: string }) {
  const wide = useMediaQuery('(min-width: 1024px)')
  const [data, setData] = useState<{ scenario: Scenario; timeline: Timeline } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [overlayRoot, setOverlayRoot] = useState<HTMLDivElement | null>(null)
  const [printing, setPrinting] = useState(false)

  useEffect(() => {
    fetchShared(token)
      .then((d) =>
        d.timeline
          ? setData({ scenario: d.scenario, timeline: d.timeline })
          : setError('Tego planu nie da się już pokazać według obecnych zasad. Poproś o nowy link.'),
      )
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Nie udało się otworzyć planu.'))
  }, [token])

  const items = useMemo(() => (data ? timelineItems(data.timeline) : []), [data])
  const selected = items.find((i) => i.id === selectedId) ?? null

  if (error) return <Centered>{error}</Centered>
  if (!data) {
    return (
      <Centered>
        <LoaderCircle className="size-5 animate-spin" /> Otwieram plan…
      </Centered>
    )
  }
  const { timeline, scenario } = data
  const situation = timeline.notes.find((n) => n.kind === 'situation')
  const deadlines = timeline.documents
    .filter((d) => d.deadline && d.deadline >= timeline.today)
    .sort((a, b) => (a.deadline ?? '').localeCompare(b.deadline ?? ''))

  return (
    <div className="relative min-h-dvh bg-white">
      <header className="flex items-center gap-3 border-b border-line px-4 py-3 lg:px-8">
        <Brand />
        <span className="ml-auto flex items-center gap-2 rounded-full bg-navy-50 px-3 py-1.5 text-xs font-bold text-navy-700">
          <Eye className="size-3.5" /> Plan udostępniony · tylko do odczytu
        </span>
      </header>
      <main className="mx-auto max-w-[1400px] px-4 pt-6 pb-16 lg:px-8">
        <p className="text-sm font-bold text-navy-500">Wasz plan</p>
        {situation && (
          <>
            <h1 className="mt-1 text-[26px] leading-tight font-bold tracking-tight text-navy-900 lg:text-[32px]">
              {situation.title}
            </h1>
            <p className="mt-2 max-w-3xl text-[17px] leading-relaxed text-navy-700">{situation.text}</p>
          </>
        )}
        <button
          type="button"
          disabled={printing}
          onClick={async () => {
            setPrinting(true)
            try {
              await (await import('@/lib/pdf/documents')).downloadPlan(timeline, scenario)
            } finally {
              setPrinting(false)
            }
          }}
          className="mt-4 flex h-10 items-center gap-2 rounded-full border border-line px-4 text-sm font-bold text-navy-700 hover:bg-navy-50"
        >
          {printing ? <LoaderCircle className="size-4 animate-spin" /> : <Printer className="size-4" />}
          Plan na kartce A4 (PDF)
        </button>

        <section className="mt-6" aria-label="Oś czasu">
          {wide ? (
            <TimelineCard
              timeline={timeline}
              changedIds={NO_CHANGES}
              changeVersion={0}
              selectedId={selectedId}
              onSelect={setSelectedId}
              overlayRoot={overlayRoot}
            />
          ) : (
            <MobileTimeline
              timeline={timeline}
              changedIds={NO_CHANGES}
              changeVersion={0}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </section>

        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          {deadlines.length > 0 && (
            <section className="rounded-4xl border border-line px-5 py-5">
              <h2 className="text-lg font-bold text-navy-900">Terminy wniosków</h2>
              <ul className="mt-3 divide-y divide-line">
                {deadlines.map((d) => (
                  <li key={d.id} className="flex items-baseline justify-between gap-3 py-2.5">
                    <span className="text-navy-900">{d.title}</span>
                    <span className="shrink-0 text-sm font-bold text-sun-700 tabular-nums">
                      najpóźniej {formatShortDate(d.deadline!)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {timeline.monthly.length > 0 && timeline.money_total && (
            <section className="rounded-4xl border border-line px-5 py-5">
              <h2 className="text-lg font-bold text-navy-900">Pieniądze miesiąc po miesiącu</h2>
              <ul className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-3">
                {timeline.monthly.map((m) => (
                  <li key={m.month} className="flex justify-between gap-2 tabular-nums">
                    <span className="text-navy-500">
                      {m.month.slice(5)}.{m.month.slice(0, 4)}
                    </span>
                    <span className={m.total > 0 ? 'font-bold text-navy-900' : 'text-navy-300'}>{formatPln(m.total)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 font-bold text-navy-900">Razem: {formatPln(timeline.money_total.total)}</p>
            </section>
          )}
        </div>
      </main>
      <div ref={setOverlayRoot} className="pointer-events-none absolute inset-0 z-20" />
      {wide ? (
        <AnimatePresence>
          {selected && (
            <Dialog key="details" label={selected.title} onClose={() => setSelectedId(null)}>
              <ElementDetails item={selected} timeline={timeline} onSelect={setSelectedId} />
            </Dialog>
          )}
        </AnimatePresence>
      ) : (
        <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelectedId(null)} title={selected?.title ?? 'Szczegóły'}>
          {selected && <ElementDetails item={selected} timeline={timeline} onSelect={setSelectedId} />}
        </Sheet>
      )}
    </div>
  )
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-dvh items-center justify-center gap-2 px-6 text-center text-navy-500">{children}</div>
}
