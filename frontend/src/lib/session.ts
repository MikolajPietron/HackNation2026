// The id of this browser's conversation. The conversation itself is stored by the backend
// (Supabase); the browser only remembers which one is its own.

const KEY = 'przewodnik-session-id'

function randomId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  // crypto.randomUUID needs a secure context; this also works over plain http on a LAN.
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

/** The stored id, or a new one. Without localStorage the conversation lasts until reload. */
export function currentSessionId(): string {
  try {
    const stored = localStorage.getItem(KEY)
    if (stored) return stored
  } catch {
    // Storage blocked (private mode): fall through to a fresh id.
  }
  return newSessionId()
}

export function newSessionId(): string {
  const id = randomId()
  try {
    localStorage.setItem(KEY, id)
  } catch {
    // Storage blocked: the id lives only in memory.
  }
  return id
}
