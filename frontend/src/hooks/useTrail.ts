// The way back between windows that open one another (an element's details, its money, the
// request to fill in, "Dlaczego tyle?"): moving from one window to the next keeps the previous one
// as a breadcrumb. A window opened from the plan (or by the assistant) starts without a trail, and
// going to a window already on the trail cuts the trail there, so it never loops.
import { useState } from 'react'

export interface Trail<P> {
  /** The windows before the current one, oldest first; empty when it was opened from the plan. */
  trail: P[]
  /** For the page transition: 1 = forward, -1 = back, 0 = opened from the plan. */
  direction: number
  /** From the current window to `to`; returns `to`, for the caller to show it. */
  forward: (to: P) => P
  /** Back to the window at `index` of the trail; returns it, for the caller to show it. */
  back: (index: number) => P
  /** A window opened or closed from outside: no trail. */
  reset: () => void
}

export function useTrail<P>(current: P | null, same: (a: P, b: P) => boolean): Trail<P> {
  const [nav, setNav] = useState<{ trail: P[]; at: P; direction: number } | null>(null)
  // The trail belongs to the window it led to: once something else opened a window, it is gone.
  const valid = nav !== null && current !== null && same(nav.at, current)
  const trail = valid ? nav.trail : []
  return {
    trail,
    direction: valid ? nav.direction : 0,
    forward: (to) => {
      if (current === null || same(current, to)) return to
      const path = [...trail, current]
      const seen = path.findIndex((p) => same(p, to))
      setNav(
        seen >= 0
          ? { trail: path.slice(0, seen), at: to, direction: -1 }
          : { trail: path, at: to, direction: 1 },
      )
      return to
    },
    back: (index) => {
      const to = trail[index]
      setNav({ trail: trail.slice(0, index), at: to, direction: -1 })
      return to
    },
    reset: () => setNav(null),
  }
}
