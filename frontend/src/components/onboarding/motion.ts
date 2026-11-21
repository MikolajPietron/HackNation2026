// Onboarding motion, built on Spectrum UI's tokens (lib/ease.ts) and its blur-in entrances.
//
// A step does not animate itself on the way in, only its children do (title, subtitle, cards)
// in a stagger, so there is one motion per element and the title always comes first.
// On the way out the whole step fades quickly as one piece.
import type { Variants } from 'motion/react'
import { EASE_IN_OUT, EASE_OUT } from '@/lib/ease'

export const STEP: Variants = {
  enter: {},
  center: { transition: { staggerChildren: 0.06, delayChildren: 0.03 } },
  exit: { opacity: 0, filter: 'blur(4px)', transition: { duration: 0.18, ease: EASE_IN_OUT } },
}

/** One element inside a step: title, subtitle, a card. */
export const ITEM: Variants = {
  enter: { opacity: 0, y: 14, filter: 'blur(4px)' },
  center: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.45, ease: EASE_OUT } },
}

/** Illustrations on the first and the last screen pop in. */
export const POP: Variants = {
  enter: { opacity: 0, scale: 0.9, y: 10, filter: 'blur(6px)' },
  center: {
    opacity: 1,
    scale: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.6, ease: EASE_OUT },
  },
}
