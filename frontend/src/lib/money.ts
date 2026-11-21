// Guide section G: amounts as the engine computed them (timeline.payments), in Polish wording.
// The frontend never computes an amount; it only formats the engine's numbers.
import type { Payment, Timeline } from '../types'

const group = (whole: string) => whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')

/** 6903.2 -> "6 903,20 zł", grouped like the engine's text. */
export function formatPln(amount: number): string {
  const [whole, cents] = amount.toFixed(2).split('.')
  return `${group(whole)},${cents} zł`
}

/** 6903.2 -> "6 903 zł", for a narrow clip. */
export const formatPlnShort = (amount: number) => `${group(Math.round(amount).toString())} zł`

/** 81.5 -> "81,5%" */
export const formatRate = (rate: number) => `${String(rate).replace('.', ',')}%`

/** The benefit for a period, if the engine computed one. */
export function paymentFor(timeline: Timeline, segmentId: string): Payment | undefined {
  return timeline.payments.find((p) => p.segment_id === segmentId)
}
