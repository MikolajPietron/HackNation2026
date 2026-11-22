// The width of a label as the browser will draw it (Lato, bold), so the timeline puts a name
// inside a clip only when it fits, instead of cutting it with "…". Measured on a canvas once per
// text and size; until the font has loaded the fallback's widths are a little off, so the cache
// is cleared when it has (`whenFontsReady`).

let context: CanvasRenderingContext2D | null | undefined
const cache = new Map<string, number>()

export function textWidth(text: string, px: number, weight = 700): number {
  const key = `${weight}|${px}|${text}`
  const hit = cache.get(key)
  if (hit !== undefined) return hit
  if (context === undefined) {
    try {
      context = document.createElement('canvas').getContext('2d')
    } catch {
      context = null
    }
  }
  let width = text.length * px * 0.55
  if (context) {
    context.font = `${weight} ${px}px Lato, 'Helvetica Neue', Helvetica, Arial, sans-serif`
    width = context.measureText(text).width
  }
  cache.set(key, width)
  return width
}

/** The root font size: "Większy tekst" scales rem, and the labels with it. */
export const remPx = () => {
  try {
    return parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
  } catch {
    return 16
  }
}

/** Runs `then` once the page's fonts are in, with the old widths forgotten. */
export function whenFontsReady(then: () => void): void {
  const fonts = typeof document !== 'undefined' ? document.fonts : undefined
  if (!fonts) return
  void fonts.ready.then(() => {
    cache.clear()
    then()
  })
}
