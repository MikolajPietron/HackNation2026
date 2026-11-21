import type { ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { durationLabel, formatDate, formatLongDate, formatRange } from '@/lib/dates'
import { sourceLabel, TONE } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { SourceRef, Timeline } from '@/types'
import type { TimelineItem } from './items'

interface Props {
  item: TimelineItem
  timeline: Timeline
  onSelect: (id: string) => void
}

/** What the parent needs about one element: when, what it means, what to prepare, the source. */
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
      const documents = timeline.documents.filter((d) => d.segment_id === s.id)
      return (
        <>
          <Header
            eyebrow={`Mama · ${TONE[s.tone].label.toLowerCase()}`}
            eyebrowClass={s.tone === 'work' ? 'text-navy-500' : 'text-zus-700'}
            title={s.title}
            subtitle={
              <>
                {formatRange(s.start, s.end)}
                <span className="font-normal text-navy-500"> · {durationLabel(s.days)}</span>
              </>
            }
          />
          <p>{s.summary}</p>
          <Bullets items={s.details} />
          {documents.length > 0 && (
            <ul className="space-y-1.5">
              {documents.map((d) => (
                <li key={d.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(d.id)}
                    className="flex w-full items-center gap-3 rounded-2xl bg-sun-100/60 px-4 py-2.5 text-left text-sm transition-colors hover:bg-sun-100"
                  >
                    <span className="min-w-0 flex-1 font-bold text-navy-900">{d.title}</span>
                    <span className="shrink-0 text-xs font-bold text-sun-700">
                      {d.done ? 'mama już je ma' : `na ${formatDate(d.needed_by)}`}
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
            eyebrowClass="text-sun-700"
            title={m.title}
            subtitle={formatLongDate(m.date)}
          />
          <p>{m.summary}</p>
          <Bullets items={m.details} />
        </>
      )
    }
    case 'document': {
      const d = item.element
      const segment = timeline.segments.find((s) => s.id === d.segment_id)
      return (
        <>
          <Header
            eyebrow="Dokument"
            eyebrowClass="text-sun-700"
            title={d.title}
            subtitle={
              <>
                Potrzebne na: {formatLongDate(d.needed_by)}
                <span
                  className={cn(
                    'ml-2 rounded-full px-2 py-0.5 text-xs font-bold',
                    d.done ? 'bg-zus-100 text-zus-700' : 'bg-sun-100 text-sun-700',
                  )}
                >
                  {d.done ? 'mama już je ma' : 'do zdobycia'}
                </span>
              </>
            }
          />
          <p>{d.rule}</p>
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

const GUIDE_QUOTES_SHOWN = 2

/**
 * Literal quotes. The card stays short: the first quotes from the guide are open, the rest of
 * them and the Labour Code wait behind toggles.
 */
function Sources({ sources }: { sources: SourceRef[] }) {
  const guide = sources.filter((s) => s.doc === 'przewodnik')
  const law = sources.filter((s) => s.doc === 'kp')
  if (sources.length === 0) return null
  const more = guide.slice(GUIDE_QUOTES_SHOWN)
  return (
    <section className="space-y-2">
      <p className="text-xs font-black tracking-widest text-navy-500 uppercase">Źródło</p>
      {guide.slice(0, GUIDE_QUOTES_SHOWN).map((source) => (
        <Quote key={source.quote} source={source} />
      ))}
      {more.length > 0 && (
        <More label={`Więcej z Przewodnika ZUS (${more.length})`} sources={more} />
      )}
      {law.length > 0 && (
        <More
          label={`Podstawa prawna: Kodeks pracy (${law.length})`}
          sources={law}
          open={guide.length === 0}
        />
      )}
    </section>
  )
}

function More({ label, sources, open }: { label: string; sources: SourceRef[]; open?: boolean }) {
  return (
    <details open={open}>
      <summary className="cursor-pointer text-sm font-bold text-zus-700">{label}</summary>
      <div className="mt-2 space-y-2">
        {sources.map((source) => (
          <Quote key={source.quote} source={source} />
        ))}
      </div>
    </details>
  )
}

function Quote({ source }: { source: SourceRef }) {
  return (
    <figure className="rounded-2xl border-l-4 border-zus-300 bg-zus-50 px-4 py-3">
      <blockquote className="text-sm text-navy-700 italic">„{source.quote}”</blockquote>
      <figcaption className="mt-1 text-xs font-bold text-zus-700">{sourceLabel(source)}</figcaption>
    </figure>
  )
}
