// Makes the facts in a sentence stand out at a glance: dates, numbers of weeks and days,
// percentages and amounts are bold. Also tidies a doubled full stop after an abbreviation
// ("20 tyg.." from the engine's text).
import { Fragment } from 'react'
import { cn } from '@/lib/utils'

const FACT =
  /(\d{1,2}\.\d{2}\.\d{4}|\d{1,2} (?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)(?: \d{4})?|\d+(?:[.,]\d+)?\s?(?:tyg\.|tygodni|tygodnie|tydzień|dni|dzień|miesięcy|miesiące|%|zł))/g

export function Emphasis({ text, className }: { text: string; className?: string }) {
  const clean = text.replace(/\.\.(?=\s|$)/g, '.')
  const parts = clean.split(FACT)
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <strong key={index} className={cn('font-bold text-navy-900', className)}>
            {part}
          </strong>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  )
}
