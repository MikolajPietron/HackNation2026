import { useCallback, useRef, useState } from 'react'
import { streamChat } from '../api'
import type { Scenario, Timeline } from '../types'

export type ToolStatus = 'running' | 'done' | 'failed'

export type MessagePart =
  | { kind: 'text'; text: string }
  | { kind: 'tool'; id: string; name: string; args: Record<string, unknown>; status: ToolStatus }

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  parts: MessagePart[]
  status: 'streaming' | 'done'
  error?: string
}

export interface ChangeSet {
  ids: string[]
  version: number
}

let lastId = 0
const nextId = () => `m${++lastId}`

function appendText(message: ChatMessage, delta: string): ChatMessage {
  const parts = [...message.parts]
  const last = parts.at(-1)
  if (last?.kind === 'text') parts[parts.length - 1] = { ...last, text: last.text + delta }
  else parts.push({ kind: 'text', text: delta })
  return { ...message, parts }
}

interface Options {
  /** A tool changed the scenario and the timeline was recalculated around `focusId`. */
  onTimeline?: (focusId: string | null) => void
  /** The assistant explains a timeline element. */
  onFocus?: (elementId: string) => void
}

/**
 * Conversation with the assistant. The client keeps the opaque history and the scenario and
 * sends them with every message; the backend streams text, tool calls and timeline updates.
 */
export function useAssistant({ onTimeline, onFocus }: Options = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [busy, setBusy] = useState(false)
  const [timeline, setTimeline] = useState<Timeline | null>(null)
  const [changed, setChanged] = useState<ChangeSet>({ ids: [], version: 0 })
  const history = useRef<unknown[]>([])
  const scenario = useRef<Scenario | undefined>(undefined)
  const request = useRef<AbortController | null>(null)

  const send = useCallback(
    async (text: string) => {
      if (request.current) return
      const controller = new AbortController()
      request.current = controller
      setBusy(true)
      const assistantId = nextId()
      setMessages((all) => [
        ...all,
        { id: nextId(), role: 'user', status: 'done', parts: [{ kind: 'text', text }] },
        { id: assistantId, role: 'assistant', status: 'streaming', parts: [] },
      ])
      const patch = (update: (message: ChatMessage) => ChatMessage) =>
        setMessages((all) => all.map((m) => (m.id === assistantId ? update(m) : m)))

      try {
        await streamChat(
          { message: text, history: history.current, scenario: scenario.current },
          (event) => {
            switch (event.type) {
              case 'text':
                patch((m) => appendText(m, event.delta))
                break
              case 'tool-call':
                patch((m) => ({
                  ...m,
                  parts: [
                    ...m.parts,
                    { kind: 'tool', id: event.id, name: event.name, args: event.args, status: 'running' },
                  ],
                }))
                break
              case 'tool-result':
                patch((m) => ({
                  ...m,
                  parts: m.parts.map((p) =>
                    p.kind === 'tool' && p.id === event.id
                      ? { ...p, status: event.ok ? 'done' : 'failed' }
                      : p,
                  ),
                }))
                break
              case 'timeline':
                scenario.current = event.scenario
                setTimeline(event.timeline)
                setChanged((c) => ({ ids: event.changed, version: c.version + 1 }))
                onTimeline?.(event.focus)
                break
              case 'focus':
                onFocus?.(event.element_id)
                break
              case 'done':
                history.current = event.history
                break
              case 'error':
                patch((m) => ({ ...m, error: event.message }))
                break
            }
          },
          controller.signal,
        )
      } catch (error) {
        // Stopped by the user: keep what has arrived, without an error.
        if (!controller.signal.aborted) {
          const message = error instanceof Error ? error.message : 'Nie udało się wysłać wiadomości.'
          patch((m) => ({ ...m, error: message }))
        }
      } finally {
        patch((m) => ({ ...m, status: 'done' }))
        if (request.current === controller) {
          request.current = null
          setBusy(false)
        }
      }
    },
    [onTimeline, onFocus],
  )

  /** Stop the answer that is being written. */
  const stop = useCallback(() => request.current?.abort(), [])

  /** Forget the conversation and the timeline and start again. */
  const reset = useCallback(() => {
    request.current?.abort()
    request.current = null
    history.current = []
    scenario.current = undefined
    setBusy(false)
    setMessages([])
    setTimeline(null)
    setChanged({ ids: [], version: 0 })
  }, [])

  return { messages, busy, send, stop, reset, timeline, changed }
}
