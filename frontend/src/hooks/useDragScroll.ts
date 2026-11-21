import { useEffect, useRef } from 'react'

/** Momentum after a flick: share of the velocity kept per millisecond. */
const GLIDE_DECAY = 0.995
/** Pixels the pointer has to travel before a press becomes a drag (a shorter move is a click). */
const DRAG_THRESHOLD = 4

/**
 * Sideways scrolling by dragging with the mouse, with momentum after a flick, like a carousel.
 * Touch and trackpads keep their native scrolling. A drag never ends in a click on a child.
 * While dragging the element has `data-dragging`.
 */
export function useDragScroll<T extends HTMLElement>() {
  const ref = useRef<T>(null)

  useEffect(() => {
    const element = ref.current
    if (!element) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let frame = 0
    let drag: { x: number; left: number; lastX: number; lastT: number; v: number; moved: boolean } | null =
      null

    const swallowClick = (event: MouseEvent) => {
      event.stopPropagation()
      event.preventDefault()
    }

    const onDown = (event: PointerEvent) => {
      cancelAnimationFrame(frame)
      if (event.pointerType !== 'mouse' || event.button !== 0) return
      drag = {
        x: event.clientX,
        left: element.scrollLeft,
        lastX: event.clientX,
        lastT: event.timeStamp,
        v: 0,
        moved: false,
      }
    }
    const onMove = (event: PointerEvent) => {
      if (!drag) return
      const dx = event.clientX - drag.x
      if (!drag.moved) {
        if (Math.abs(dx) < DRAG_THRESHOLD) return
        drag.moved = true
        element.setPointerCapture(event.pointerId)
        element.dataset.dragging = 'true'
      }
      element.scrollLeft = drag.left - dx
      const dt = event.timeStamp - drag.lastT
      if (dt > 0) drag.v = 0.8 * ((event.clientX - drag.lastX) / dt) + 0.2 * drag.v
      drag.lastX = event.clientX
      drag.lastT = event.timeStamp
    }
    const onUp = () => {
      const current = drag
      drag = null
      if (!current?.moved) return
      delete element.dataset.dragging
      element.addEventListener('click', swallowClick, true)
      window.setTimeout(() => element.removeEventListener('click', swallowClick, true), 0)
      if (reduce || Math.abs(current.v) < 0.05) return
      let velocity = current.v
      let last = performance.now()
      const step = (now: number) => {
        const dt = now - last
        last = now
        element.scrollLeft -= velocity * dt
        velocity *= Math.pow(GLIDE_DECAY, dt)
        const atEdge =
          element.scrollLeft <= 0 || element.scrollLeft >= element.scrollWidth - element.clientWidth
        if (Math.abs(velocity) > 0.02 && !atEdge) frame = requestAnimationFrame(step)
      }
      frame = requestAnimationFrame(step)
    }

    element.addEventListener('pointerdown', onDown)
    element.addEventListener('pointermove', onMove)
    element.addEventListener('pointerup', onUp)
    element.addEventListener('pointercancel', onUp)
    return () => {
      cancelAnimationFrame(frame)
      element.removeEventListener('pointerdown', onDown)
      element.removeEventListener('pointermove', onMove)
      element.removeEventListener('pointerup', onUp)
      element.removeEventListener('pointercancel', onUp)
    }
  }, [])

  return ref
}
