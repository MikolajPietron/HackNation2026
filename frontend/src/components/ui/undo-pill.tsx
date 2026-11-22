// The "Undo" pill after a change made from the interface (FUNKCJE: zmiana planu bez czatu).
// A ring around "Cofnij" drains for 5 seconds; the pill pauses while the pointer or the focus is
// on it, and Escape undoes (unless a window is open, where Escape closes the window). The timing
// is a CSS animation, so pausing the ring and pausing the countdown are the same thing.
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Check, Hourglass, LoaderCircle, RotateCcw, TriangleAlert } from 'lucide-react'
import type { PlanChange } from '@/hooks/usePlanChange'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { cn } from '@/lib/utils'

const SECONDS = 5
const R = 15
const CIRCUMFERENCE = 2 * Math.PI * R

export function UndoPill({
  change,
  onUndo,
  onDismiss,
}: {
  change: PlanChange | null
  onUndo: () => void
  onDismiss: () => void
}) {
  return (
    <AnimatePresence>
      {change && <Pill key={change.id} change={change} onUndo={onUndo} onDismiss={onDismiss} />}
    </AnimatePresence>
  )
}

function Pill({ change, onUndo, onDismiss }: { change: PlanChange; onUndo: () => void; onDismiss: () => void }) {
  const [paused, setPaused] = useState(false)
  const canUndo = change.status === 'done' && change.undo !== null

  // Escape undoes, but a window that is open gets Escape first.
  useEffect(() => {
    if (!canUndo) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || document.querySelector('[role="dialog"]')) return
      event.preventDefault()
      onUndo()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [canUndo, onUndo])

  // Messages without the ring (undone, refused) close by themselves a little later.
  useEffect(() => {
    if (change.status === 'done' || change.status === 'working') return
    const timer = window.setTimeout(onDismiss, change.status === 'error' ? 6000 : change.status === 'wait' ? 3500 : 2400)
    return () => window.clearTimeout(timer)
  }, [change.status, onDismiss])

  const tone = change.status === 'error' ? 'error' : 'calm'
  return (
    <motion.div
      role="status"
      aria-live="polite"
      initial={{ opacity: 0, y: 14, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.98, transition: { duration: 0.16 } }}
      transition={{ duration: 0.26, ease: EASE_OUT }}
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      className={cn(
        'fixed inset-x-4 bottom-24 z-[60] mx-auto flex max-w-xl items-center gap-3 rounded-3xl py-2 pr-2 pl-4 text-sm text-white shadow-[0_18px_40px_-18px_rgb(26_36_56/0.6)]',
        'lg:inset-x-auto lg:bottom-6 lg:left-1/2 lg:-translate-x-1/2 lg:rounded-full',
        tone === 'error' ? 'bg-alert-600' : 'bg-navy-900',
      )}
    >
      <span className="shrink-0" aria-hidden>
        {change.status === 'working' ? (
          <LoaderCircle className="size-4 animate-spin text-white/80" />
        ) : change.status === 'error' ? (
          <TriangleAlert className="size-4 text-sun-300" />
        ) : change.status === 'wait' ? (
          <Hourglass className="size-4 text-sun-300" />
        ) : (
          <Check className="size-4 text-zus-300" />
        )}
      </span>
      <span className="min-w-0 flex-1 py-1.5 leading-snug">
        <span className="font-bold">{change.title}</span>
        {change.detail && <span className="block text-white/75">{change.detail}</span>}
      </span>
      {canUndo && (
        <motion.button
          type="button"
          onClick={onUndo}
          whileTap={{ scale: 0.96, transition: SPRING_PRESS }}
          className="relative flex h-10 shrink-0 items-center gap-2 rounded-full bg-white/12 pr-4 pl-1 font-bold transition-colors hover:bg-white/20 focus-visible:ring-2 focus-visible:ring-white/60 focus-visible:outline-none"
        >
          <span className="relative grid size-8 place-items-center">
            <svg viewBox="0 0 36 36" className="absolute inset-0 size-8 -rotate-90" aria-hidden>
              <circle cx="18" cy="18" r={R} fill="none" stroke="rgb(255 255 255 / 0.18)" strokeWidth="2.5" />
              <circle
                cx="18"
                cy="18"
                r={R}
                fill="none"
                stroke="white"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeDasharray={CIRCUMFERENCE}
                style={{
                  animation: `undo-drain ${SECONDS}s linear forwards`,
                  animationPlayState: paused ? 'paused' : 'running',
                  ['--undo-length' as string]: `${CIRCUMFERENCE}`,
                }}
                onAnimationEnd={onDismiss}
              />
            </svg>
            <RotateCcw className="size-3.5" />
          </span>
          Cofnij
          <span className="sr-only"> (Escape)</span>
        </motion.button>
      )}
      {!canUndo && change.status !== 'working' && (
        <button
          type="button"
          onClick={onDismiss}
          className="h-10 shrink-0 rounded-full px-4 font-bold text-white/80 transition-colors hover:bg-white/10 hover:text-white focus-visible:ring-2 focus-visible:ring-white/60 focus-visible:outline-none"
        >
          OK
        </button>
      )}
    </motion.div>
  )
}
