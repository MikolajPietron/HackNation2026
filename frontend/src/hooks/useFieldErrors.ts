// When a field's format error shows: once the field is left (blur) or the form is submitted, not
// while it is typed the first time. A shown error follows the typing ("brakuje 2" → "brakuje 1")
// and goes away as soon as the value is right; a field that was right waits for the next blur
// before it complains again.
import { useCallback, useMemo, useState } from 'react'
import type { FieldTone } from '@/components/ui/field-error'

export function useFieldErrors() {
  const [armed, setArmed] = useState<ReadonlySet<string>>(() => new Set())
  const edit = useCallback(
    (change: (keys: Set<string>) => void) =>
      setArmed((previous) => {
        const next = new Set(previous)
        change(next)
        return next
      }),
    [],
  )
  return useMemo(
    () => ({
      /** The message to show now, or null. */
      shown: (key: string, message: string | null) => (message && armed.has(key) ? message : null),
      /** The field was left: its error, if any, shows from now on. */
      blur: (key: string, message: string | null) => {
        if (message && !armed.has(key)) edit((keys) => keys.add(key))
      },
      /** The field was typed in; `message` is its error for the new value. */
      change: (key: string, message: string | null) => {
        if (!message && armed.has(key)) edit((keys) => keys.delete(key))
      },
      /** Submit: every field with an error shows it. */
      showAll: (keys: string[]) => edit((all) => keys.forEach((key) => all.add(key))),
    }),
    [armed, edit],
  )
}

/** The border and the focus ring of a field with an issue; nothing when it has none. */
export function fieldLook(tone: FieldTone | null | undefined): string {
  if (tone === 'error') return 'border-alert-600 hover:border-alert-600 focus:border-alert-600 focus:ring-alert-600/15'
  if (tone === 'warning') return 'border-sun-400 hover:border-sun-400 focus:border-sun-400 focus:ring-sun-400/30'
  return ''
}
