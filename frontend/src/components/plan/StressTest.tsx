// "Co, jeśli coś pójdzie inaczej?" (FUNKCJE F11): the plan tested against every event that can
// still happen (POST /api/stress, no AI), as tiles to scan at a glance: the event, the engine's
// verdict (the rights stay, a new risk, something is lost) and one figure of the engine — the
// money on the plan after the event, or its first line. A tile shows the event on the real axis
// (hooks/usePlanSpotlight): the plan as a shadow, the engine's lines in the banner over it,
// nothing saved. The mother's illness, stay in hospital or death are behind their own toggle and
// worded gently (the engine marks them `sensitive`).
import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowRight, ChevronDown, Eye, LoaderCircle } from 'lucide-react'
import { ITEM } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { STRESS_ICON, VERDICT } from '@/lib/stress'
import { formatPln } from '@/lib/money'
import { cn } from '@/lib/utils'
import type { StressEvent, StressEventId, StressReport, StressVerdict } from '@/types'


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
  const count = (verdict: StressVerdict) => plain.filter((e) => e.verdict === verdict).length

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
              ? summary(count('kept'), count('risk'), count('loss'))
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
          {plain.map((event, index) => (
            <Tile
              key={event.id}
              event={event}
              index={index}
              active={active === event.id}
              loading={loading === event.id}
              disabled={loading !== null}
              onPreview={() => onPreview(event.id)}
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
                      event={event}
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

/** "8 zdarzeń nic Wam nie zabiera, 1 niesie ryzyko, 1 coś zabiera." */
function summary(kept: number, risk: number, loss: number): string {
  // 2-4 take the plural verb; 1 and 5+ the singular ("5 zdarzeń niesie").
  const few = (n: number) => n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)
  const parts = []
  if (kept) {
    const noun = kept === 1 ? 'zdarzenie' : few(kept) ? 'zdarzenia' : 'zdarzeń'
    parts.push(`${kept} ${noun} nic Wam nie ${few(kept) ? 'zabierają' : 'zabiera'}`)
  }
  if (risk) parts.push(`${risk} ${few(risk) ? 'niosą' : 'niesie'} ryzyko`)
  if (loss) parts.push(`${loss} coś ${few(loss) ? 'zabierają' : 'zabiera'}`)
  return `${parts.join(', ')}. Kliknij zdarzenie, a pokażemy je na Waszej osi.`
}

function Tile({
  event,
  index,
  active,
  loading,
  disabled,
  onPreview,
  gentle = false,
}: {
  event: StressEvent
  index: number
  active: boolean
  loading: boolean
  disabled: boolean
  onPreview: () => void
  gentle?: boolean
}) {
  const verdict = VERDICT[event.verdict]
  const diff = event.money?.diff ?? null
  const figure = !gentle && diff !== null && diff !== 0
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
          'group relative flex h-full min-h-40 w-full flex-col overflow-hidden rounded-3xl border bg-white p-4 text-left',
          'transition-[border-color,box-shadow,background-color] duration-200 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
          active
            ? 'border-navy-900 bg-navy-50/60 shadow-[0_0_0_1px_var(--color-navy-900)]'
            : 'border-line hover:border-navy-200 hover:shadow-[0_16px_40px_-28px_rgb(26_36_56/0.45)]',
        )}
      >
        {!gentle && <span aria-hidden className={cn('absolute inset-x-0 top-0 h-1', verdict.bar)} />}
        <span className="flex items-start justify-between gap-2">
          <Illustration src={STRESS_ICON[event.id]} size="event" className="bg-navy-50/60" />
          {!gentle && <span className={cn('rounded-full px-2 py-0.5 text-xs font-bold', verdict.chip)}>{verdict.label}</span>}
        </span>
        <span className="mt-3 leading-tight font-bold text-navy-900">{event.title}</span>
        {figure ? (
          <span className="mt-1.5">
            <span className={cn('block text-xl font-bold tabular-nums', diff > 0 ? 'text-zus-700' : 'text-sun-700')}>
              {diff > 0 ? '+' : '−'}
              {formatPln(Math.abs(diff))}
            </span>
            <span className="block text-xs font-bold text-navy-400">zasiłki razem na osi</span>
          </span>
        ) : (
          event.lines[0] && <span className="mt-1.5 text-sm text-pretty text-navy-500">{event.lines[0]}</span>
        )}
        <span
          className={cn(
            'mt-auto flex items-center gap-1.5 pt-3 text-sm font-bold',
            active ? 'text-navy-900' : 'text-zus-700',
          )}
        >
          {loading ? (
            <>
              <LoaderCircle className="size-4 animate-spin" /> Liczę…
            </>
          ) : active ? (
            <>
              <Eye className="size-4" /> Na osi teraz
            </>
          ) : (
            <>
              Pokaż na osi <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </>
          )}
        </span>
      </motion.button>
    </motion.li>
  )
}
