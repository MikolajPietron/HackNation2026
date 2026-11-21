import { useCallback, useEffect, useRef, useState } from 'react'
import { deleteSession, fetchSession, streamChat } from '../api'
import { currentSessionId, newSessionId } from '../lib/session'
import type { StoredMessage, StoredPart, Timeline } from '../types'

export type MessagePart = StoredPart
export type ToolStatus = Extract<StoredPart, { kind: 'tool' }>['status']

export interface ChatMessage extends StoredMessage {
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
 * Conversation with the assistant. The backend stores it per session id (Supabase), so a
 * reload brings the chat and the timeline back. The browser keeps only the id.
 */
export function useAssistant({ onTimeline, onFocus }: Options = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [busy, setBusy] = useState(false)
  const [restoring, setRestoring] = useState(true)
  const [timeline, setTimeline] = useState<Timeline | null>(null)
  const [changed, setChanged] = useState<ChangeSet>({ ids: [], version: 0 })
  const sessionId = useRef(currentSessionId())
  const request = useRef<AbortController | null>(null)

  // Pick up the stored conversation after a reload.
  useEffect(() => {
    let cancelled = false
    fetchSession(sessionId.current)
      .then((session) => {
        if (cancelled) return
        setMessages((current) => (current.length === 0 ? session.messages : current))
        setTimeline((current) => current ?? session.timeline)
      })
      .catch(() => {
        // Backend unreachable: start empty; sending a message will show the error.
      })
      .finally(() => {
        if (!cancelled) setRestoring(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

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
          { session_id: sessionId.current, message: text },
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
                setTimeline(event.timeline)
                setChanged((c) => ({ ids: event.changed, version: c.version + 1 }))
                onTimeline?.(event.focus)
                break
              case 'focus':
                onFocus?.(event.element_id)
                break
              case 'error':
                patch((m) => ({ ...m, error: event.message }))
                break
              case 'done':
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

  /** Forget the conversation and the timeline (also on the server) and start again. */
  const reset = useCallback(() => {
    request.current?.abort()
    request.current = null
    void deleteSession(sessionId.current).catch(() => undefined)
    sessionId.current = newSessionId()
    setBusy(false)
    setMessages([])
    setTimeline(null)
    setChanged({ ids: [], version: 0 })
  }, [])

  return { messages, busy, restoring, send, stop, reset, timeline, changed }
}
