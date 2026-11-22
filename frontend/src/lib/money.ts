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

const byStart = (a: Payment, b: Payment) => a.start.localeCompare(b.start)

/** One parent's payments in date order. */
export const paymentsOf = (timeline: Timeline, lane: Payment['lane']) =>
  timeline.payments.filter((p) => p.lane === lane).sort(byStart)

/**
 * The payment that answers "how much do we get?": the one going on today, else the next one,
 * else the last one; the mother's first, the father's when the mother has none.
 */
export function headlinePayment(timeline: Timeline): { now: Payment; then?: Payment } | null {
  for (const lane of ['mother', 'father'] as const) {
    const list = paymentsOf(timeline, lane)
    if (list.length === 0) continue
    const index = Math.max(0, list.findIndex((p) => p.end >= timeline.today))
    const now = list[index] ?? list[list.length - 1]
    const then = list.slice(index + 1).find((p) => p.monthly !== now.monthly)
    return { now, then }
  }
  return null
}

/** The engine's own points about money: the amounts, who pays, 100/70 or 81,5%. */
export const moneyNote = (timeline: Timeline, id: 'money' | 'payer' | 'rate-815') =>
  timeline.notes.find((n) => n.id === id)
