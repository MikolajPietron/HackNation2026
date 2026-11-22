// What the parents have already filed or gathered, ticked by hand on the plan (FUNKCJE: the
// checklist "Co dołączyć"). Kept in this browser for this conversation: a document id
// ("parental-request") or a document's attachment ("parental-request/za-zyciem").
import { useCallback, useSyncExternalStore } from 'react'
import { currentSessionId } from '@/lib/session'
import type { Document, Timeline } from '@/types'

const EVENT = 'zpr-done'
const key = () => `zpr-done-${currentSessionId()}`

let cached: { key: string; raw: string | null; done: Set<string> } | null = null

function read(): Set<string> {
  const k = key()
  let raw: string | null = null
  try {
    raw = window.localStorage.getItem(k)
  } catch {
    raw = cached?.key === k ? cached.raw : null
  }
  if (cached && cached.key === k && cached.raw === raw) return cached.done
  let done = new Set<string>()
  try {
    done = new Set(raw ? (JSON.parse(raw) as string[]) : [])
  } catch {
    done = new Set()
  }
  cached = { key: k, raw, done }
  return done
}

function write(done: Set<string>) {
  const raw = JSON.stringify([...done])
  try {
    window.localStorage.setItem(key(), raw)
  } catch {
    cached = { key: key(), raw, done }
  }
  window.dispatchEvent(new Event(EVENT))
}

function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}

/** The ticked ids and a toggle, live across the plan's components. */
export function useDone(): [Set<string>, (id: string) => void] {
  const done = useSyncExternalStore(subscribe, read, () => new Set<string>())
  const toggle = useCallback((id: string) => {
    const next = new Set(read())
    if (next.has(id)) next.delete(id)
    else next.add(id)
    write(next)
  }, [])
  return [done, toggle]
}

/** Documents still to file (or filed today), the soonest first. */
export function documentsToFile(timeline: Timeline): Document[] {
  return [...timeline.documents]
    .filter((d) => d.needed_by >= timeline.today || (d.deadline !== null && !d.done))
    .sort((a, b) => (a.deadline ?? a.needed_by).localeCompare(b.deadline ?? b.needed_by))
}
