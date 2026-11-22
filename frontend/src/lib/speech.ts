// "Czytaj na głos" with the browser's own speech (Web Speech API): free, no service of ours.
// Only a Polish voice installed on the device is used, so the text never leaves it (a cloud
// voice, e.g. Chrome's "Google polski", would send it to its provider). Without such a voice the
// menu does not offer reading at all.
import { useSyncExternalStore } from 'react'

const synth = typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null
// Chrome loads the voices lazily: ask once early, so they are there when the menu opens.
synth?.getVoices()

let current: SpeechSynthesisUtterance | null = null
const listeners = new Set<() => void>()
const notify = () => listeners.forEach((listener) => listener())

const polishVoice = () =>
  synth?.getVoices().find((voice) => voice.lang.toLowerCase().startsWith('pl') && voice.localService) ?? null

/** Whether this device can read Polish aloud on its own. */
export const canReadAloud = () => polishVoice() !== null

/** The selected text, or else what the plan marks to be read (`data-read-aloud`): the situation. */
function textToRead(): string {
  const selected = window.getSelection()?.toString().trim()
  if (selected) return selected
  return [...document.querySelectorAll<HTMLElement>('[data-read-aloud]')]
    .map((element) => element.innerText.trim())
    .filter(Boolean)
    .join('. ')
}

export function readAloud() {
  const voice = polishVoice()
  const text = textToRead()
  if (!synth || !voice || !text) return
  synth.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.voice = voice
  utterance.lang = voice.lang
  // The cancelled utterance ends after the new one starts: only the current one may stop it.
  utterance.onend = utterance.onerror = () => {
    if (current !== utterance) return
    current = null
    notify()
  }
  current = utterance
  synth.speak(utterance)
  notify()
}

export function stopReading() {
  current = null
  synth?.cancel()
  notify()
}

/** Whether the app is reading aloud right now. */
export function useReading() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => current !== null,
  )
}
