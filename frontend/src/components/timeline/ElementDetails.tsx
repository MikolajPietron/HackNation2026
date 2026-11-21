import type { ReactNode } from 'react'
import { durationLabel, formatDate, formatLongDate, formatRange } from '../../lib/dates'
import { cx, LANE, sourceLabel } from '../../lib/ui'
import type { SourceRef, Timeline } from '../../types'
import type { TimelineItem } from './items'

interface Props {
  item: TimelineItem
  timeline: Timeline
  onSelect: (id: string) => void
}

export function ElementDetails({ item, timeline, onSelect }: Props) {
  return (
    <div className="space-y-4 text-sm leading-relaxed text-stone-700">
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
                <span className="font-normal text-stone-500"> · {durationLabel(s.days)}</span>
              </>
            }
          />
          <p>{s.summary}</p>
          <dl className="grid gap-x-4 gap-y-1.5 rounded-xl bg-stone-50 p-3 sm:grid-cols-[auto_1fr]">
            <dt className="text-stone-500">Świadczenie</dt>
            <dd className="font-medium text-stone-900">{s.benefit}</dd>
            <dt className="text-stone-500">Kto wypłaca</dt>
            <dd>{s.payer}</dd>
          </dl>
          <Bullets items={s.details} />
          {applications.length > 0 && (
            <div>
              <p className="mb-1.5 font-medium text-stone-900">Wnioski</p>
              <ul className="space-y-1.5">
                {applications.map((a) => (
                  <li key={a.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(a.id)}
                      className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left ring-1 ring-stone-200 transition hover:bg-stone-50"
                    >
                      <span>{a.title}</span>
                      <span
                        className={cx(
                          'shrink-0 text-xs font-semibold',
                          a.passed ? 'text-red-700' : 'text-stone-600',
                        )}
                      >
                        {a.is_deadline ? `do ${formatDate(a.due)}` : formatDate(a.due)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
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
                  <span className="ml-2 rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700 ring-1 ring-red-200">
                    termin minął
                  </span>
                )}
              </>
            }
          />
          <p>{a.rule}</p>
          <div className="rounded-xl bg-stone-50 p-3">
            <p className="text-stone-500">Gdzie złożyć</p>
            <p className="font-medium text-stone-900">{a.where}</p>
          </div>
          {segment && (
            <button
              type="button"
              onClick={() => onSelect(segment.id)}
              className="text-sm font-medium text-teal-700 underline-offset-2 hover:underline"
            >
              Dotyczy: {segment.title} →
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
    <header>
      <p className={cx('text-xs font-semibold tracking-wide uppercase', eyebrowClass)}>{eyebrow}</p>
      <h3 className="mt-1 text-lg leading-snug font-semibold text-stone-900">{title}</h3>
      <p className="mt-1 font-medium text-stone-900">{subtitle}</p>
    </header>
  )
}

function Bullets({ items }: { items: string[] }) {
  if (items.length === 0) return null
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((text) => (
        <li key={text}>{text}</li>
      ))}
    </ul>
  )
}

function Sources({ sources }: { sources: SourceRef[] }) {
  const first = sources.slice(0, 2)
  const rest = sources.slice(2)
  return (
    <section>
      <p className="mb-2 font-medium text-stone-900">Źródła</p>
      <div className="space-y-2">
        {first.map((source, index) => (
          <Quote key={index} source={source} />
        ))}
      </div>
      {rest.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-semibold text-teal-700">
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
    <figure className="rounded-lg border-l-4 border-stone-300 bg-stone-50 px-3 py-2">
      {source.quote && (
        <blockquote className="text-[13px] text-stone-700 italic">„{source.quote}”</blockquote>
      )}
      <figcaption className="mt-1 text-xs font-semibold text-stone-500">
        {sourceLabel(source)}
      </figcaption>
    </figure>
  )
}
