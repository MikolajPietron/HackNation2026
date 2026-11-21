import type { ChatEvent, ChatRequest } from './types'

/** Empty in dev: Vite forwards /api to the backend. Set VITE_API_URL for a separate API host. */
export const API_URL: string = import.meta.env.VITE_API_URL ?? ''

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
  } catch {
    throw new Error('Brak połączenia z serwerem. Sprawdź, czy backend działa (npm run dev).')
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
