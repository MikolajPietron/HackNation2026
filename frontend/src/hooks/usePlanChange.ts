// Changes to the plan made from the interface, without the chat (the 81,5% choice, a plan for a
// goal, the parental plan): PATCH /api/session/{id}/scenario, then the timeline is replaced and
// what changed lights up. Every change can be undone for a moment: the undo is the same PATCH
// with the fields as they were before.
import { useCallback, useRef, useState } from 'react'
import { changeScenario } from '@/api'
import { currentSessionId } from '@/lib/session'
import type { Scenario, ScenarioChanges, SessionStart } from '@/types'

export interface PlanChange {
  id: number
  status: 'working' | 'done' | 'undone' | 'error' | 'wait'
  title: string
  detail?: string
  /** The fields as they were before; null once undone or when the change failed. */
  undo: ScenarioChanges | null
}

/** Change the plan from the interface; resolves to whether the engine accepted it. */
export type PlanApply = (changes: ScenarioChanges, title: string, detail?: string) => Promise<boolean>

export function usePlanChange(scenario: Scenario | null, onUpdate: (start: SessionStart) => void) {
  const [change, setChange] = useState<PlanChange | null>(null)
  const counter = useRef(0)
  const busy = useRef(false)

  const apply = useCallback(
    async (changes: ScenarioChanges, title: string, detail?: string): Promise<boolean> => {
      if (!scenario || busy.current) return false
      busy.current = true
      const id = ++counter.current
      const undo = Object.fromEntries(
        Object.keys(changes).map((key) => [key, scenario[key as keyof Scenario] ?? null]),
      ) as ScenarioChanges
      setChange({ id, status: 'working', title: 'Przeliczam plan…', undo: null })
      try {
        onUpdate(await changeScenario(currentSessionId(), changes))
        setChange({ id, status: 'done', title, detail, undo })
        return true
      } catch (error) {
        setChange({
          id,
          status: 'error',
          title: 'Nie da się tak zmienić planu',
          detail: error instanceof Error ? error.message : undefined,
          undo: null,
        })
        return false
      } finally {
        busy.current = false
      }
    },
    [scenario, onUpdate],
  )

  const undo = useCallback(async () => {
    if (!change?.undo || busy.current) return
    busy.current = true
    const { id, undo: before } = change
    setChange({ id, status: 'working', title: 'Cofam…', undo: null })
    try {
      onUpdate(await changeScenario(currentSessionId(), before))
      setChange({ id, status: 'undone', title: 'Cofnięte', detail: 'Plan jest taki jak wcześniej.', undo: null })
    } catch (error) {
      setChange({
        id,
        status: 'error',
        title: 'Nie udało się cofnąć',
        detail: error instanceof Error ? error.message : undefined,
        undo: null,
      })
    } finally {
      busy.current = false
    }
  }, [change, onUpdate])

  const dismiss = useCallback(() => setChange(null), [])

  /** A change asked for while it cannot be made yet (the assistant is still writing). */
  const wait = useCallback((title: string, detail?: string) => {
    setChange({ id: ++counter.current, status: 'wait', title, detail, undo: null })
  }, [])

  return { change, apply, undo, dismiss, wait, working: change?.status === 'working' }
}
