import type { ChatEvent, ChatRequest, SessionView, Timeline } from './types'

/** Empty in dev: Vite forwards /api to the backend. Set VITE_API_URL for a separate API host. */
export const API_URL: string = import.meta.env.VITE_API_URL ?? ''

const OFFLINE = 'Brak połączenia z serwerem. Sprawdź, czy backend działa (npm run dev).'

/** One assistant turn. The backend streams NDJSON: one ChatEvent per line. */
export async function streamChat(
  request: ChatRequest,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error(OFFLINE)
  }
  if (!response.ok || !response.body) {
    throw new Error(await errorDetail(response))
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line) as ChatEvent)
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as ChatEvent)
}

/** The stored conversation and its timeline; empty for a new session. */
export async function fetchSession(sessionId: string): Promise<SessionView> {
  const response = await fetch(`${API_URL}/api/session/${sessionId}`)
  if (!response.ok) throw new Error(await errorDetail(response))
  return (await response.json()) as SessionView
}

/** Onboarding: store the due date as the first answer of the interview; returns the timeline. */
export async function startSession(
  sessionId: string,
  dueDate: string,
  signal?: AbortSignal,
): Promise<Timeline> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/session/${sessionId}/due-date`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ due_date: dueDate }),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error(OFFLINE)
  }
  if (!response.ok) throw new Error(await errorDetail(response))
  return (await response.json()) as Timeline
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${API_URL}/api/session/${sessionId}`, { method: 'DELETE' })
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // Not JSON: fall through to the generic message.
  }
  return `Serwer odpowiedział błędem ${response.status}.`
}
