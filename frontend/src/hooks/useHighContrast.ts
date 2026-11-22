import { useEffect, useState } from 'react'

const KEY = 'high-contrast'
const CLASS = 'contrast'

/** Whether the parent turned the high contrast on; kept in this browser only. */
function stored(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

// Applied as soon as the app loads, also on the start screen (index.css: html.contrast).
document.documentElement.classList.toggle(CLASS, stored())

/** "Wysoki kontrast" (WCAG): darker text, lines and borders, a stronger focus ring. Shared by
 *  both menus, like "Większy tekst". */
export function useHighContrast(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => document.documentElement.classList.contains(CLASS))
  useEffect(() => {
    document.documentElement.classList.toggle(CLASS, on)
    try {
      localStorage.setItem(KEY, on ? '1' : '0')
    } catch {
      // Private mode: the setting lasts until the page is closed.
    }
  }, [on])
  return [on, setOn]
}
