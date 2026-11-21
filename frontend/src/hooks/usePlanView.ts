// Which view of the plan the parent picked (the axis or the wall calendar), remembered on this
// device. Browser storage can be missing or blocked; then it is the axis and nothing breaks.
import { useState } from 'react'

export type PlanView = 'axis' | 'calendar'

const KEY = 'plan-view'

/** The remembered view; browser storage can be missing or blocked, so it falls back to the axis. */
export function usePlanView(): [PlanView, (view: PlanView) => void] {
  const [view, setView] = useState<PlanView>(() => {
    try {
      return window.localStorage.getItem(KEY) === 'calendar' ? 'calendar' : 'axis'
    } catch {
      return 'axis'
    }
  })
  const choose = (next: PlanView) => {
    setView(next)
    try {
      window.localStorage.setItem(KEY, next)
    } catch {
      // Not remembered; the switch still works.
    }
  }
  return [view, choose]
}
