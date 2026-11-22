// The banner over the axis after the plan changed, or while a what-if is shown on it
// (hooks/usePlanSpotlight). A change: what was added, moved or is gone, each opening its details;
// the axis rings the same elements and keeps the old plan as a shadow. A preview: the event, the
// engine's verdict and lines, the money before and after (the engine's totals), the dates it
// assumed, and the way back. "To się stało" hands the event to the assistant, which asks for the
// real facts: the what-if's dates are made up, so it is never saved as it is. When the parent
// scrolls away from the banner of a preview, a pill at the bottom keeps the way back at hand (in a
// portal: the plan's sections animate with filters, which would pin a fixed element inside them).
// Not while the page itself scrolls up to the banner: the pill would only flash for a moment.
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, ChevronRight, Eye, MessageCircle, X } from 'lucide-react'
import { Illustration } from '@/components/ui/illustration'
import type { Spotlight } from '@/hooks/usePlanSpotlight'
import type { ChangeItem } from '@/lib/diff'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { formatPln } from '@/lib/money'
import { HAPPENED, REASON, STRESS_ICON, VERDICT } from '@/lib/stress'
import { cn } from '@/lib/utils'
import type { StressEvent, StressEventId } from '@/types'

const SIGN: Record<ChangeItem['kind'], { mark: string; tone: string }> = {
  added: { mark: '+', tone: 'bg-zus-50 text-zus-700' },
  removed: { mark: '−', tone: 'bg-sun-100 text-sun-700' },
  moved: { mark: '↔', tone: 'bg-navy-50 text-navy-700' },
  money: { mark: 'zł', tone: 'bg-navy-50 text-navy-700' },
}

const SHOWN = 6

export function ChangeBanner({
  banner,
  loading,
  error,
  onSelect,
  onDismiss,
  onSwitch,
  onHappened,
}: {
  banner: Spotlight | null
  loading: StressEventId | null
  error: string | null
  onSelect: (id: string) => void
  onDismiss: () => void
  /** Show another variant of the same event (the reason for a job loss). */
  onSwitch: (id: StressEventId) => void
  onHappened: (prompt: string) => void
}) {
  return (
    <>
      <AnimatePresence initial={false} mode="popLayout">
        {banner?.kind === 'change' && (
          <motion.div
            key="change"
            initial={{ opacity: 0, y: -8, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, height: 0, transition: { duration: 0.18 } }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <ChangeCard items={banner.items} onSelect={onSelect} onDismiss={onDismiss} />
          </motion.div>
        )}
        {banner?.kind === 'preview' && (
          <motion.div
            key={`preview-${banner.event.id}`}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.15 } }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
          >
            <PreviewCard
              event={banner.event}
              events={banner.events}
              loading={loading}
              onDismiss={onDismiss}
              onSwitch={onSwitch}
              onHappened={onHappened}
            />
          </motion.div>
        )}
      </AnimatePresence>
      {error && (
        <p role="alert" className="mb-3 flex items-center gap-2 rounded-2xl bg-alert-50 px-4 py-2.5 text-sm font-bold text-alert-600">
          {error}
        </p>
      )}
    </>
  )
}

function ChangeCard({
  items,
  onSelect,
  onDismiss,
}: {
  items: ChangeItem[]
  onSelect: (id: string) => void
  onDismiss: () => void
}) {
  const [all, setAll] = useState(false)
  const visible = all ? items : items.slice(0, SHOWN)
  return (
    <section
      aria-live="polite"
      aria-label="Co się zmieniło w planie"
      className="mb-3 rounded-3xl border border-sun-300 bg-sun-100/40 px-4 py-3 sm:px-5"
    >
      <div className="flex items-start gap-3">
        <span className="mt-1 size-2.5 shrink-0 rounded-full bg-sun-400 motion-safe:animate-pulse" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-bold text-navy-900">Plan się zmienił</p>
          <p className="text-sm text-navy-500">
            Na osi zmiany mają bursztynową obwódkę, a cień pokazuje, jak było. Kliknij zmianę, żeby
            zobaczyć szczegóły.
          </p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Zamknij"
          className="-mt-1 -mr-2 grid size-8 shrink-0 place-items-center rounded-full text-navy-400 transition-colors hover:bg-white hover:text-navy-900"
        >
          <X className="size-4" />
        </button>
      </div>
      <ul className="mt-2.5 flex flex-wrap gap-2">
        {visible.map((item, index) => (
          <motion.li
            key={item.key}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: Math.min(index, 6) * 0.04, ease: EASE_OUT }}
          >
            <button
              type="button"
              disabled={!item.id}
              onClick={() => item.id && onSelect(item.id)}
              className="group flex max-w-full items-center gap-2 rounded-2xl border border-line bg-white py-1.5 pr-3 pl-1.5 text-left text-sm transition-[border-color,box-shadow] duration-150 enabled:hover:border-navy-200 enabled:hover:shadow-sm disabled:opacity-80"
            >
              <span className={cn('grid h-6 min-w-6 shrink-0 place-items-center rounded-full px-1 text-xs font-black', SIGN[item.kind].tone)}>
                {SIGN[item.kind].mark}
              </span>
              <Illustration src={item.icon} size="hint" />
              <span className="min-w-0">
                <span className={cn('font-bold text-navy-900', item.kind === 'removed' && 'line-through decoration-navy-300')}>
                  {item.title}
                </span>
                <span className="text-navy-500"> · {item.detail}</span>
              </span>
              {item.id && <ChevronRight className="size-3.5 shrink-0 text-navy-300 group-hover:text-navy-500" />}
            </button>
          </motion.li>
        ))}
        {items.length > SHOWN && (
          <li>
            <button
              type="button"
              onClick={() => setAll(!all)}
              className="h-full rounded-2xl px-3 py-1.5 text-sm font-bold text-zus-700 hover:bg-white"
            >
              {all ? 'Mniej' : `i ${items.length - SHOWN} więcej`}
            </button>
          </li>
        )}
      </ul>
    </section>
  )
}

function PreviewCard({
  event,
  events,
  loading,
  onDismiss,
  onSwitch,
  onHappened,
}: {
  event: StressEvent
  events: StressEvent[]
  loading: StressEventId | null
  onDismiss: () => void
  onSwitch: (id: StressEventId) => void
  onHappened: (prompt: string) => void
}) {
  const box = useRef<HTMLElement>(null)
  const [away, setAway] = useState(false)
  // The preview opens far below the axis and the page scrolls up to it: the banner is out of view
  // for that moment. The pill waits until the banner has been seen (or, if the page never got
  // there, a moment longer than the scroll takes).
  const [seen, setSeen] = useState(false)
  const [more, setMore] = useState(false)
  const verdict = VERDICT[event.verdict]
  const money = event.money
  const variants = event.id.startsWith('job-loss-') ? events.filter((e) => REASON[e.id]) : []
  const happened = event.sensitive ? undefined : HAPPENED[event.id]
  const lines = more ? event.lines : event.lines.slice(0, 4)

  // The pill at the bottom while the banner is out of view.
  useEffect(() => {
    const element = box.current
    if (!element) return
    const observer = new IntersectionObserver(([entry]) => {
      setAway(!entry.isIntersecting)
      if (entry.isIntersecting) setSeen(true)
    })
    observer.observe(element)
    const late = window.setTimeout(() => setSeen(true), 1500)
    return () => {
      observer.disconnect()
      window.clearTimeout(late)
    }
  }, [])

  return (
    <>
      <section
        ref={box}
        aria-live="polite"
        aria-label={`Podgląd: ${event.title}`}
        className="mb-3 rounded-3xl border-2 border-dashed border-sun-400 bg-sun-100/35 px-4 py-4 sm:px-5"
      >
        <div className="flex flex-wrap items-start gap-3">
          <Illustration src={STRESS_ICON[event.id]} size="event" className="bg-white" />
          <div className="min-w-0 flex-1 basis-[calc(100%-3rem)] sm:basis-auto">
            <p className="flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1 rounded-full bg-navy-900 px-2 py-0.5 text-[11px] font-black tracking-wide text-white uppercase">
                <Eye className="size-3" /> Podgląd
              </span>
              {!event.sensitive && (
                <span className={cn('rounded-full px-2 py-0.5 text-xs font-bold', verdict.chip)}>{verdict.label}</span>
              )}
            </p>
            <h3 className="mt-1 text-lg leading-tight font-bold text-navy-900">{event.title}</h3>
            <p className="mt-0.5 text-sm text-navy-500">
              Tak wyglądałby Wasz plan. Nic nie zapisujemy — cień na osi to plan, który macie teraz.
            </p>
          </div>
          <div className="flex w-full shrink-0 items-center gap-2 sm:w-auto">
            <motion.button
              type="button"
              onClick={onDismiss}
              whileTap={{ scale: 0.96, transition: SPRING_PRESS }}
              className="flex h-10 items-center gap-2 rounded-full bg-navy-900 px-4 text-sm font-bold text-white transition-colors hover:bg-navy-700"
            >
              <ArrowLeft className="size-4" /> Wróć do planu
            </motion.button>
          </div>
        </div>

        {variants.length > 1 && (
          <div role="radiogroup" aria-label="Powód utraty pracy" className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-sm font-bold text-navy-500">Powód:</span>
            {variants.map((variant) => (
              <button
                key={variant.id}
                type="button"
                role="radio"
                aria-checked={variant.id === event.id}
                onClick={() => onSwitch(variant.id)}
                disabled={loading !== null}
                className={cn(
                  'h-8 rounded-full border px-3 text-sm font-bold transition-colors',
                  variant.id === event.id
                    ? 'border-navy-900 bg-navy-900 text-white'
                    : 'border-line bg-white text-navy-700 hover:border-navy-200',
                )}
              >
                {REASON[variant.id]}
              </button>
            ))}
          </div>
        )}

        <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="min-w-0 text-sm">
            {event.plan_breaks && (
              <p className="mb-2 rounded-2xl bg-sun-100 px-3 py-2 font-bold text-sun-700">{event.plan_breaks}</p>
            )}
            <ul className="space-y-1">
              {lines.map((line) => (
                <li key={line} className="flex gap-2 text-navy-900">
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-sun-400" />
                  {line}
                </li>
              ))}
            </ul>
            {(event.lines.length > 4 || event.risks.length > 0 || event.assumed.length > 0) && (
              <button
                type="button"
                onClick={() => setMore(!more)}
                aria-expanded={more}
                className="mt-1.5 font-bold text-zus-700 underline-offset-4 hover:underline"
              >
                {more ? 'Mniej' : 'Więcej: ryzyka i założenia'}
              </button>
            )}
            <AnimatePresence initial={false}>
              {more && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
                  transition={{ duration: 0.24, ease: EASE_OUT }}
                  className="overflow-hidden"
                >
                  {event.risks.map((risk) => (
                    <p key={risk.id} className="mt-2 rounded-2xl bg-white px-3 py-2 text-sun-700">
                      <b className="text-navy-900">{risk.title}.</b> {risk.text}
                    </p>
                  ))}
                  {event.assumed.length > 0 && (
                    <p className="mt-2 text-xs leading-relaxed text-navy-500">
                      <b>Przyjęliśmy do podglądu:</b> {event.assumed.join(' ')}
                    </p>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          {money && money.diff !== 0 && (
            <div className="rounded-2xl bg-white px-4 py-3 text-sm lg:min-w-56">
              <p className="font-bold text-navy-500">Wszystkie zasiłki na osi</p>
              <p className="mt-1 text-navy-500 tabular-nums">
                {formatPln(money.total_before)} <span aria-hidden>→</span>
              </p>
              <p className="text-lg font-bold text-navy-900 tabular-nums">{formatPln(money.total_after)}</p>
              <p className={cn('mt-0.5 font-bold tabular-nums', money.diff > 0 ? 'text-zus-700' : 'text-sun-700')}>
                {money.diff > 0 ? '+' : '−'}
                {formatPln(Math.abs(money.diff))}
              </p>
            </div>
          )}
        </div>

        {happened && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-sun-300/60 pt-3">
            <button
              type="button"
              onClick={() => onHappened(happened)}
              className="flex h-9 items-center gap-2 rounded-full border border-line bg-white px-3.5 text-sm font-bold text-navy-700 transition-colors hover:border-navy-200"
            >
              <MessageCircle className="size-4" /> To się stało — powiedz asystentowi
            </button>
            <span className="text-xs text-navy-500">Asystent dopyta o prawdziwe daty i zapisze je w planie.</span>
          </div>
        )}
      </section>

      {createPortal(
        <AnimatePresence>
          {away && seen && (
          <motion.div
            key="pill"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8, transition: { duration: 0.15 } }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            className="fixed bottom-20 left-4 z-40 flex items-center gap-3 rounded-full bg-navy-900 py-1.5 pr-1.5 pl-4 text-sm font-bold text-white shadow-[0_18px_40px_-18px_rgb(26_36_56/0.6)] lg:bottom-8 lg:left-8"
          >
            <Eye className="size-4 text-sun-300" />
            <span>Oglądacie podgląd</span>
            <button
              type="button"
              onClick={() => box.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              className="rounded-full px-2.5 py-1.5 text-white/80 hover:bg-white/10 hover:text-white"
            >
              Pokaż
            </button>
            <button
              type="button"
              onClick={onDismiss}
              className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-navy-900 hover:bg-sun-100"
            >
              <ArrowLeft className="size-3.5" /> Wróć do planu
            </button>
          </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </>
  )
}
