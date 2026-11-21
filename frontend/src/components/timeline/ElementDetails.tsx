import type { ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { durationLabel, formatDate, formatLongDate, formatRange } from '@/lib/dates'
import { LANE, sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { SourceRef, Timeline } from '@/types'
import type { TimelineItem } from './items'

interface Props {
  item: TimelineItem
  timeline: Timeline
  onSelect: (id: string) => void
}

/** What the parent needs about one element: when, how much, who pays, what to file, and the source. */
export function ElementDetails({ item, timeline, onSelect }: Props) {
  return (
    <div className="space-y-4 text-[15px] leading-relaxed text-navy-700">
      <Body item={item} timeline={timeline} onSelect={onSelect} />
      <Sources sources={item.element.sources} />
    </div>
  )
}

function Body({ item, timeline, onSelect }: Props) {
  switch (item.kind) {
    case 'segment': {
      const s = item.element
      const applications = timeline.applications.filter((a) => a.segment_id === s.id)
      return (
        <>
          <Header
            eyebrow={`${LANE[s.lane].label}${s.is_example ? ' · przykładowy termin' : ''}`}
            eyebrowClass={LANE[s.lane].text}
            title={s.title}
            subtitle={
              <>
                {formatRange(s.start, s.end)}
                <span className="font-normal text-navy-500"> · {durationLabel(s.days)}</span>
              </>
            }
          />
          <p>{s.summary}</p>
          <dl className="grid gap-x-5 gap-y-1.5 rounded-2xl bg-canvas p-4 text-sm sm:grid-cols-[auto_1fr]">
            <dt className="text-navy-500">Świadczenie</dt>
            <dd className="font-bold text-navy-900">{s.benefit}</dd>
            <dt className="text-navy-500">Kto wypłaca</dt>
            <dd>{s.payer}</dd>
          </dl>
          <Bullets items={s.details} />
          {applications.length > 0 && (
            <ul className="space-y-1.5">
              {applications.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(a.id)}
                    className="flex w-full items-center gap-3 rounded-2xl bg-sun-100/60 px-4 py-2.5 text-left text-sm transition-colors hover:bg-sun-100"
                  >
                    <span className="min-w-0 flex-1 font-bold text-navy-900">{a.title}</span>
                    <span
                      className={cn(
                        'shrink-0 text-xs font-bold',
                        a.passed ? 'text-alert-600' : 'text-sun-700',
                      )}
                    >
                      {a.is_deadline ? `do ${formatDate(a.due)}` : formatDate(a.due)}
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-sun-700" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )
    }
    case 'marker': {
      const m = item.element
      return (
        <>
          <Header
            eyebrow="Ważny dzień"
            eyebrowClass={LANE.child.text}
            title={m.title}
            subtitle={formatLongDate(m.date)}
          />
          <p>{m.summary}</p>
          <Bullets items={m.details} />
        </>
      )
    }
    case 'application': {
      const a = item.element
      const segment = timeline.segments.find((s) => s.id === a.segment_id)
      return (
        <>
          <Header
            eyebrow={`Wniosek · ${a.parent === 'mother' ? 'mama' : 'tata'}`}
            eyebrowClass={LANE.applications.text}
            title={a.title}
            subtitle={
              <>
                {a.is_deadline ? 'Termin: do ' : 'Potrzebny na: '}
                {formatLongDate(a.due)}
                {a.passed && (
                  <span className="ml-2 rounded-full bg-alert-50 px-2 py-0.5 text-xs font-bold text-alert-600">
                    termin minął
                  </span>
                )}
              </>
            }
          />
          <p>{a.rule}</p>
          <div className="rounded-2xl bg-canvas p-4 text-sm">
            <p className="text-navy-500">Gdzie złożyć</p>
            <p className="font-bold text-navy-900">{a.where}</p>
          </div>
          {segment && (
            <button
              type="button"
              onClick={() => onSelect(segment.id)}
              className="flex items-center gap-1 text-sm font-bold text-zus-700 underline-offset-2 hover:underline"
            >
              Dotyczy: {segment.title}
              <ChevronRight className="size-4" />
            </button>
          )}
        </>
      )
    }
  }
}

function Header({
  eyebrow,
  eyebrowClass,
  title,
  subtitle,
}: {
  eyebrow: string
  eyebrowClass: string
  title: string
  subtitle: ReactNode
}) {
  return (
    <header className="pr-8">
      <p className={cn('text-xs font-black tracking-widest uppercase', eyebrowClass)}>{eyebrow}</p>
      <h3 className="mt-1 text-xl leading-snug font-black text-navy-900">{title}</h3>
      <p className="mt-1 font-bold text-navy-900">{subtitle}</p>
    </header>
  )
}

function Bullets({ items }: { items: string[] }) {
  if (items.length === 0) return null
  return (
    <ul className="list-disc space-y-1 pl-5 marker:text-zus-400">
      {items.map((text) => (
        <li key={text}>{text}</li>
      ))}
    </ul>
  )
}

/** One quote up front; the rest behind a toggle so the card stays short. */
function Sources({ sources }: { sources: SourceRef[] }) {
  const [first, ...rest] = sources
  if (!first) return null
  return (
    <section>
      <p className="mb-2 text-xs font-black tracking-widest text-navy-500 uppercase">Źródło</p>
      <Quote source={first} />
      {rest.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm font-bold text-zus-700">
            Więcej źródeł ({rest.length})
          </summary>
          <div className="mt-2 space-y-2">
            {rest.map((source, index) => (
              <Quote key={index} source={source} />
            ))}
          </div>
        </details>
      )}
    </section>
  )
}

function Quote({ source }: { source: SourceRef }) {
  return (
    <figure className="rounded-2xl border-l-4 border-zus-300 bg-zus-50 px-4 py-3">
      {source.quote && (
        <blockquote className="text-sm text-navy-700 italic">„{source.quote}”</blockquote>
      )}
      <figcaption className="mt-1 text-xs font-bold text-zus-700">{sourceLabel(source)}</figcaption>
    </figure>
  )
}
