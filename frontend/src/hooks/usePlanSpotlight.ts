// One way for every change of the plan to be seen (FUNKCJE F16): whatever recalculated the
// timeline (the assistant, a button on the plan, a plan for a goal, the 81,5% choice), the page
// scrolls to the axis, a banner over it says what changed (lib/diff.ts) and the playhead stands on
// the first change; the axis itself rings the changed elements and keeps the old plan as a shadow.
//
// The same place shows a what-if of the stress test (F11) on the real axis: the event's timeline
// from POST /api/stress (computed by the engine, nothing saved) in place of the plan, the plan as
// the shadow, the engine's own lines in the banner. The list of events comes without timelines
// (small); the timelines (large) are fetched once per plan, on the first preview.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useReducedMotion } from 'motion/react'
import { stressTest } from '@/api'
import { dayNumber } from '@/lib/dates'
import { describeChange, firstChangedDay } from '@/lib/diff'
import type { ChangeItem } from '@/lib/diff'
import type { Scenario, StressEvent, StressEventId, StressReport, Timeline } from '@/types'
import type { ChangeSet } from './useAssistant'

export type Spotlight =
  | { kind: 'change'; items: ChangeItem[] }
  | { kind: 'preview'; event: StressEvent; events: StressEvent[] }

interface Preview {
  event: StressEvent
  events: StressEvent[]
  timeline: Timeline
}

/** The list of what-ifs for a scenario; `scenario` says which plan it is for. */
interface Report {
  scenario: Scenario
  report?: StressReport
  error?: string
}

/** The nearest ancestor that scrolls (the plan column). */
function scrollParent(element: HTMLElement): HTMLElement | null {
  for (let node = element.parentElement; node; node = node.parentElement) {
    const { overflowY } = window.getComputedStyle(node)
    if (overflowY === 'auto' || overflowY === 'scroll') return node
  }
  return null
}

export function usePlanSpotlight({
  timeline,
  scenario,
  changed,
}: {
  timeline: Timeline | null
  scenario: Scenario | null
  changed: ChangeSet
}) {
  const anchor = useRef<HTMLElement>(null)
  const reduce = useReducedMotion()
  /** Grows with every change and every preview: the scroll and the rings play again. */
  const [beat, setBeat] = useState(0)
  const [banner, setBanner] = useState<Spotlight | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [focus, setFocus] = useState<{ day: number; key: number } | null>(null)
  const [loading, setLoading] = useState<StressEventId | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [list, setList] = useState<Report | null>(null)
  const full = useRef<{ scenario: Scenario; report: Promise<StressReport> } | null>(null)
  const current = useRef(scenario)
  useEffect(() => {
    current.current = scenario
  }, [scenario])

  // A recalculated plan: say what changed. A new plan also ends a preview (it was of the old one).
  const [seen, setSeen] = useState({ timeline, scenario, version: changed.version })
  if (timeline !== seen.timeline || scenario !== seen.scenario || changed.version !== seen.version) {
    const before = seen.timeline
    setSeen({ timeline, scenario, version: changed.version })
    if (scenario !== seen.scenario && preview) {
      setPreview(null)
      setBanner(null)
    }
    if (changed.version !== seen.version && before && timeline && changed.ids.length > 0) {
      const items = describeChange(before, timeline, changed.ids)
      if (items.length > 0) {
        const next = beat + 1
        setBeat(next)
        setBanner({ kind: 'change', items })
        const day = firstChangedDay(timeline, changed.ids)
        setFocus(day ? { day: dayNumber(day), key: next } : null)
      }
    }
  }

  // The what-ifs for the plan as it is now (without timelines).
  useEffect(() => {
    if (!scenario) return
    const controller = new AbortController()
    stressTest(scenario, false, controller.signal)
      .then((report) => setList({ scenario, report }))
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setList({ scenario, error: reason instanceof Error ? reason.message : 'Nie udało się sprawdzić planu.' })
      })
    return () => controller.abort()
  }, [scenario])

  // Bring the axis into view when something new is on it, unless it is already at the top.
  useEffect(() => {
    if (beat === 0) return
    const element = anchor.current
    if (!element) return
    const scroller = scrollParent(element)
    const top = element.getBoundingClientRect().top - (scroller?.getBoundingClientRect().top ?? 0)
    const height = scroller?.clientHeight ?? window.innerHeight
    if (top >= -4 && top <= height * 0.25) return
    element.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  }, [beat, reduce])

  /** Show what an event would do, on the axis. */
  const show = async (id: StressEventId) => {
    if (!scenario || !timeline || loading) return
    if (preview?.event.id === id) {
      setBeat((b) => b + 1)
      return
    }
    setLoading(id)
    setError(null)
    try {
      if (!full.current || full.current.scenario !== scenario) {
        full.current = { scenario, report: stressTest(scenario, true) }
      }
      const report = await full.current.report
      if (current.current !== scenario) return
      const event = report.events.find((e) => e.id === id)
      if (!event?.timeline) throw new Error('Tego zdarzenia nie da się już pokazać dla Waszego planu.')
      // The axis keeps the real today; the engine counted the what-if as of its own day.
      const shown = { ...event.timeline, today: timeline.today }
      const day = firstChangedDay(shown, event.changed)
      const key = Date.now()
      setPreview({ event, events: report.events, timeline: shown })
      setBanner({ kind: 'preview', event, events: report.events })
      setFocus(day ? { day: dayNumber(day), key } : null)
      setBeat((b) => b + 1)
    } catch (reason) {
      full.current = null
      setError(reason instanceof Error ? reason.message : 'Nie udało się pokazać zdarzenia.')
    } finally {
      setLoading(null)
    }
  }

  const endPreview = () => {
    setPreview(null)
    setBanner(null)
    setFocus(null)
  }

  const dismiss = () => (preview ? endPreview() : setBanner(null))

  const realChanged = useMemo(() => new Set(changed.ids), [changed])
  const previewChanged = useMemo(() => new Set(preview?.event.changed ?? []), [preview])
  const report = list && list.scenario === scenario ? list : null

  return {
    /** Put on the section of the axis: the page scrolls to it. */
    anchor,
    banner,
    dismiss,
    /** The timeline the axis, the calendar and the steps ahead show (a preview or the plan). */
    shown: preview?.timeline ?? timeline,
    previewing: preview?.event ?? null,
    changedIds: preview ? previewChanged : realChanged,
    changeVersion: changed.version * 1000 + beat,
    /** Where the playhead goes after a change. */
    focus,
    show,
    endPreview,
    loading,
    error,
    /** The what-ifs of the plan (no timelines); null while loading. */
    report: report?.report ?? null,
    reportError: report?.error ?? null,
  }
}
