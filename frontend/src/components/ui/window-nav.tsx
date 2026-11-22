// Moving between windows that open one another (hooks/useTrail): the breadcrumbs above the
// content say where the parent came from and take them back, and the content of the next window
// slides in from the side it came from, starting at its top. Our own: Spectrum UI has no
// breadcrumbs.
import { useLayoutEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { ArrowLeft, ChevronRight } from 'lucide-react'
import { EASE_OUT } from '@/lib/ease'

/** "← Urlop macierzyński po porodzie › Zasiłek mamy": every earlier window is a link back. */
export function WindowCrumbs({
  trail,
  current,
  onBack,
}: {
  /** The names of the earlier windows, oldest first (not empty). */
  trail: string[]
  current: string
  onBack: (index: number) => void
}) {
  const parent = trail.length - 1
  return (
    <nav aria-label="Gdzie jesteś" className="flex items-start gap-2.5">
      <button
        type="button"
        onClick={() => onBack(parent)}
        aria-label={`Wróć: ${trail[parent]}`}
        className="grid size-9 shrink-0 place-items-center rounded-full border border-line text-navy-700 transition-[background-color,transform] duration-150 hover:bg-navy-50 active:scale-[0.94] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
      >
        <ArrowLeft className="size-4" />
      </button>
      <ol className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 pt-1.5 text-sm leading-snug">
        {trail.map((label, index) => (
          <li key={index} className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => onBack(index)}
              className="rounded font-bold text-zus-700 underline-offset-2 hover:text-zus-900 hover:underline focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
            >
              {label}
            </button>
            <ChevronRight aria-hidden className="size-3.5 shrink-0 text-navy-300" />
          </li>
        ))}
        <li aria-current="page" className="text-navy-500">
          {current}
        </li>
      </ol>
    </nav>
  )
}

/**
 * One window's content. A new `page` starts at the top of the scrolling box and, when the parent
 * moved there from another window, slides in from that side (`direction` 1 forward, -1 back).
 */
export function WindowPage({ page, direction, children }: { page: string; direction: number; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const scroller = box.current?.closest<HTMLElement>('[data-scroll]')
    if (scroller) scroller.scrollTop = 0
  }, [page])
  return (
    <motion.div
      key={page}
      ref={box}
      initial={direction === 0 ? false : { opacity: 0, x: direction * 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.22, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  )
}
