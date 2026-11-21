import { useEffect, useState } from 'react'

const LARGE_TEXT = '112.5%'

/** "Większy tekst": scales the whole app (Tailwind sizes are in rem). Shared by both menus. */
export function useLargeText(): [boolean, (on: boolean) => void] {
  const [largeText, setLargeText] = useState(() => document.documentElement.style.fontSize === LARGE_TEXT)
  useEffect(() => {
    document.documentElement.style.fontSize = largeText ? LARGE_TEXT : ''
  }, [largeText])
  return [largeText, setLargeText]
}
