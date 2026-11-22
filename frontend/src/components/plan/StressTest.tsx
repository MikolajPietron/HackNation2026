// "Co, jeśli coś pójdzie inaczej?" (FUNKCJE F11): the plan tested against every event that can
// still happen (POST /api/stress, no AI), as quiet tiles to scan at a glance: the event, the
// engine's verdict (the rights stay, a new risk, something is lost) and one figure of the engine —
// how the benefits on the plan change, or its first line. The job loss is one tile: its reasons
// differ only in law, and the preview switches between them. A tile shows the event on the axis
// (hooks/usePlanSpotlight): the plan as a shadow, the engine's lines in the banner over it,
// nothing saved. The mother's illness, stay in hospital or death are behind their own toggle and
// worded gently (the engine marks them `sensitive`).
import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, Eye, LoaderCircle } from 'lucide-react'
import { ITEM } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { REASON, STRESS_ICON, VERDICT } from '@/lib/stress'
import { formatShortDate } from '@/lib/dates'
import { formatPlnShort } from '@/lib/money'
import { length } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { RightChange, StressEvent, StressEventId, StressReport } from '@/types'


export function StressTest({
  report,
  error,
  active,
  loading,
  onPreview,
}: {
  /** null while it loads. */
  report: StressReport | null
  error: string | null
  /** The event shown on the axis now. */
  active: StressEventId | null
  loading: StressEventId | null
  onPreview: (id: StressEventId) => void
}) {
  const [gentleOpen, setGentleOpen] = useState(false)
  if (report?.sensitive) return null
  const events = report?.events ?? []
  const plain = events.filter((e) => !e.sensitive)
  const gentle = events.filter((e) => e.sensitive)

  return (
    <motion.section
      variants={ITEM}
      aria-labelledby="stress-test"
      className="mt-10 scroll-mt-4 rounded-4xl border border-line px-4 pt-5 pb-4 sm:px-5 lg:mt-12"
    >
      <header className="flex items-start gap-3">
        <Illustration src={ICONS.parasol} size="event" className="bg-navy-50/70" />
        <div className="min-w-0">
          <h2 id="stress-test" className="text-lg leading-tight font-bold text-navy-900">
            Co, jeśli coś pójdzie inaczej?
          </h2>
          <p className="mt-0.5 text-sm text-navy-500">
            {report && plain.length > 0
              ? 'Kliknij zdarzenie, a pokażemy je na Waszej osi. Kwota to zmiana wszystkich zasiłków w planie.'
              : 'Sprawdzamy Wasz plan na zdarzeniach, które jeszcze mogą się zdarzyć.'}
          </p>
        </div>
      </header>

      {error && (
        <p role="alert" className="mt-4 rounded-2xl bg-alert-50 px-4 py-3 text-sm font-bold text-alert-600">
          {error}
        </p>
      )}
      {!report && !error && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-40 animate-pulse rounded-3xl bg-navy-50/70" />
          ))}
        </div>
      )}
      {report?.reason && <p className="mt-4 text-sm text-navy-500">{report.reason}</p>}

      {plain.length > 0 && (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {groups(plain).map((group, index) => (
            <Tile
              key={group[0].id}
              events={group}
              index={index}
              active={active !== null && group.some((e) => e.id === active)}
              loading={loading !== null && group.some((e) => e.id === loading)}
              disabled={loading !== null}
              onPreview={() => onPreview(group[0].id)}
            />
          ))}
        </ul>
      )}

      {gentle.length > 0 && (
        <div className="mt-4 border-t border-line pt-1">
          <button
            type="button"
            onClick={() => setGentleOpen((o) => !o)}
            aria-expanded={gentleOpen}
            className="flex w-full items-center gap-2 rounded-2xl px-2 py-3 text-left text-sm font-bold text-navy-500 transition-colors hover:bg-navy-50/60"
          >
            <span className="flex-1">Trudne sytuacje mamy: choroba, szpital ({gentle.length})</span>
            <ChevronDown className={cn('size-4 transition-transform duration-200', gentleOpen && 'rotate-180')} />
          </button>
          <AnimatePresence initial={false}>
            {gentleOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
                transition={{ duration: 0.24, ease: EASE_OUT }}
                className="overflow-hidden"
              >
                <p className="px-2 pb-3 text-sm text-navy-500">
                  Co dzieje się z urlopem, gdy mama nie może opiekować się dzieckiem. Tata może wtedy
                  przejąć urlop macierzyński.
                </p>
                <ul className="grid gap-3 pb-1 sm:grid-cols-2 xl:grid-cols-3">
                  {gentle.map((event, index) => (
                    <Tile
                      key={event.id}
                      events={[event]}
                      index={index}
                      active={active === event.id}
                      loading={loading === event.id}
                      disabled={loading !== null}
                      onPreview={() => onPreview(event.id)}
                      gentle
                    />
                  ))}
                </ul>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </motion.section>
  )
}

/** The events as tiles: the job loss for every reason the work allows is one tile. */
function groups(events: StressEvent[]): StressEvent[][] {
  const jobLoss = events.filter((e) => e.id.startsWith('job-loss-'))
  const result: StressEvent[][] = []
  for (const event of events) {
    if (!event.id.startsWith('job-loss-')) result.push([event])
    else if (event === jobLoss[0]) result.push(jobLoss)
  }
  return result
}

/** "+7 047 zł", "−62 807 zł": whole złoty on a tile, the exact amount is in the preview. */
const signed = (amount: number) => `${amount > 0 ? '+' : '−'}${formatPlnShort(Math.abs(amount))}`

/** The engine's change of an entitlement in a few words: "Urlop macierzyński: 20 → 31 tyg.",
 *  "Uzupełniający urlop macierzyński: +4 tyg.", "Urlop macierzyński przepada". */
function rightLine(change: RightChange): string {
  const label = change.label.charAt(0).toUpperCase() + change.label.slice(1)
  // A number never parts from its unit or the arrow.
  const len = (days: number) => length(days).replace(' ', '\u00a0')
  if (change.days_before === 0) return `${label}: +${len(change.days_after)}`
  if (change.days_after === 0) return `${label} przepada`
  return `${label}: ${len(change.days_before)}\u00a0→\u00a0${len(change.days_after)}`
}

/** What a gentle event changes first: a right, else the period that is added (the father's
 *  leave), else the engine's first line. */
function firstChange(event: StressEvent): string | null {
  if (event.rights[0]) return rightLine(event.rights[0])
  const added = event.periods.find((p) => p.change === 'added' && p.start_after)
  if (added) return `${added.title} od ${formatShortDate(added.start_after!)}`
  return event.lines[0] ?? null
}

/** The job loss by reason: reasons with the same verdict and money read as one line. */
function byReason(events: StressEvent[]): { reasons: string[]; event: StressEvent }[] {
  const lines: { reasons: string[]; event: StressEvent }[] = []
  for (const event of events) {
    const same = lines.find((l) => l.event.verdict === event.verdict && l.event.money?.diff === event.money?.diff)
    const reason = REASON[event.id] ?? event.title
    if (same) same.reasons.push(reason)
    else lines.push({ reasons: [reason], event })
  }
  return lines
}

function Tile({
  events,
  index,
  active,
  loading,
  disabled,
  onPreview,
  gentle = false,
}: {
  /** One event, or the variants of the job loss. */
  events: StressEvent[]
  index: number
  active: boolean
  loading: boolean
  disabled: boolean
  onPreview: () => void
  gentle?: boolean
}) {
  const event = events[0]
  const many = events.length > 1
  const verdict = VERDICT[event.verdict]
  const diff = event.money?.diff ?? null
  const change = gentle ? firstChange(event) : event.rights[0] ? rightLine(event.rights[0]) : null
  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index, 8) * 0.04, ease: EASE_OUT }}
    >
      <motion.button
        type="button"
        onClick={onPreview}
        disabled={disabled && !loading}
        aria-pressed={active}
        whileTap={{ scale: 0.98, transition: SPRING_PRESS }}
        className={cn(
          'flex h-full w-full flex-col rounded-3xl border bg-white p-4 text-left sm:p-5',
          'transition-[border-color,box-shadow,background-color] duration-200 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
          active
            ? 'border-navy-900 bg-navy-50/60 shadow-[0_0_0_1px_var(--color-navy-900)]'
            : 'border-line hover:border-navy-200 hover:shadow-[0_16px_40px_-28px_rgb(26_36_56/0.45)]',
        )}
      >
        {/* The event. */}
        <span className="flex items-center gap-3">
          <Illustration src={STRESS_ICON[event.id]} size="event" className="bg-navy-50/60" />
          <span className="min-w-0 flex-1 text-[17px] leading-snug font-bold text-navy-900">
            {many ? 'Utrata pracy w ciąży' : event.title}
          </span>
        </span>

        {many ? (
          // What each reason means, money first.
          <span className="mt-4 block space-y-2">
            {byReason(events).map(({ reasons, event: e }) => {
              const d = e.money?.diff ?? null
              return (
                <span key={e.id} className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 text-sm text-navy-700">
                    <span className="font-bold text-navy-900">{reasons.join(', ')}</span>
                    {e.verdict !== 'kept' && <span className="text-navy-500"> · {VERDICT[e.verdict].label}</span>}
                  </span>
                  {d !== null && d !== 0 && (
                    <span className={cn('shrink-0 text-lg font-bold tabular-nums', d > 0 ? 'text-zus-700' : 'text-sun-700')}>
                      {signed(d)}
                    </span>
                  )}
                </span>
              )
            })}
          </span>
        ) : (
          <>
            {/* What changes in the leave, then the money. */}
            {change && (
              <span className={cn('mt-4 block text-[15px] leading-snug', gentle ? 'text-navy-700' : 'font-bold text-navy-900')}>
                {change}
              </span>
            )}
            {!gentle && diff !== null && diff !== 0 && (
              <span className="mt-2 flex items-baseline gap-2">
                <span className={cn('text-[26px] leading-none font-bold tracking-tight tabular-nums', diff > 0 ? 'text-zus-700' : 'text-sun-700')}>
                  {signed(diff)}
                </span>
                <span className="text-sm text-navy-500">zasiłków razem</span>
              </span>
            )}
          </>
        )}

        {/* The verdict, at the foot so the tiles of a row line up; and whether it is on the axis. */}
        {((!gentle && !many) || loading || active) && (
          <span className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-4 text-sm font-bold">
            {!gentle && !many && (
              <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-bold', verdict.chip)}>{verdict.label}</span>
            )}
            {loading ? (
              <span className="flex items-center gap-1.5 text-navy-900">
                <LoaderCircle className="size-4 animate-spin" /> Liczę…
              </span>
            ) : (
              active && (
                <span className="flex items-center gap-1.5 text-navy-900">
                  <Eye className="size-4" /> Na osi teraz
                </span>
              )
            )}
          </span>
        )}
      </motion.button>
    </motion.li>
  )
}
