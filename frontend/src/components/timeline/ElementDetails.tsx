import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, ChevronRight, FileText } from 'lucide-react'
import { Emphasis } from '@/components/ui/emphasis'
import { formatDayMonthLong, formatDistance, formatShortDate } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { SourceRef, Timeline } from '@/types'
import type { TimelineItem } from './items'

interface Props {
  item: TimelineItem
  timeline: Timeline
  onSelect: (id: string) => void
}

interface Fact {
  label: string
  value: string
}

/**
 * What the parent needs about one element. The facts come first and big (from, to, how long;
 * or when and how far away), the explanation with its numbers in bold, the sources last.
 */
export function ElementDetails({ item, timeline, onSelect }: Props) {
  return (
    <div className="text-[15px] leading-relaxed text-navy-700">
      <Body item={item} timeline={timeline} onSelect={onSelect} />
      <Sources sources={item.element.sources} />
    </div>
  )
}

const weeksOrDays = (days: number) => (days % 7 === 0 ? `${days / 7} tyg.` : `${days} dni`)

function Body({ item, timeline, onSelect }: Props) {
  switch (item.kind) {
    case 'segment': {
      const s = item.element
      const documents = timeline.documents.filter((d) => d.segment_id === s.id)
      return (
        <>
          <Title>{s.title}</Title>
          <Facts
            facts={[
              { label: 'Od', value: formatShortDate(s.start) },
              { label: 'Do', value: formatShortDate(s.end) },
              { label: 'Ile', value: weeksOrDays(s.days) },
            ]}
          />
          <p className="mt-5">
            <Emphasis text={s.summary} />
          </p>
          <Bullets items={s.details} />
          {documents.length > 0 && (
            <ul className="mt-5 space-y-2">
              {documents.map((d) => (
                <li key={d.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(d.id)}
                    className="group flex w-full items-center gap-3 rounded-2xl border border-line px-4 py-3 text-left transition-[border-color,transform] duration-150 hover:border-navy-200 active:scale-[0.98]"
                  >
                    <FileText className="size-4 shrink-0 text-sun-700" />
                    <span className="min-w-0 flex-1 font-bold text-navy-900">{d.title}</span>
                    <span className="shrink-0 text-sm font-bold text-navy-500">
                      {d.done ? 'już jest' : `na ${formatDayMonthLong(d.needed_by)}`}
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-navy-400 transition-transform group-hover:translate-x-0.5" />
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
          <Title>{m.title}</Title>
          <Facts
            facts={[
              { label: 'Kiedy', value: formatShortDate(m.date) },
              { label: 'Od dziś', value: formatDistance(timeline.today, m.date) },
            ]}
          />
          <p className="mt-5">
            <Emphasis text={m.summary} />
          </p>
          <Bullets items={m.details} />
        </>
      )
    }
    case 'document': {
      const d = item.element
      const segment = timeline.segments.find((s) => s.id === d.segment_id)
      return (
        <>
          <Title>{d.title}</Title>
          <Facts
            facts={[
              { label: 'Potrzebne na', value: formatShortDate(d.needed_by) },
              { label: 'Od dziś', value: formatDistance(timeline.today, d.needed_by) },
              { label: 'Status', value: d.done ? 'już jest' : 'do zdobycia' },
            ]}
          />
          <p className="mt-5">
            <Emphasis text={d.rule} />
          </p>
          {segment && (
            <button
              type="button"
              onClick={() => onSelect(segment.id)}
              className="group mt-4 flex items-center gap-1 text-sm font-bold text-zus-700"
            >
              Dotyczy: {segment.title}
              <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </button>
          )}
        </>
      )
    }
  }
}

function Title({ children }: { children: string }) {
  return (
    <h3 className="pr-10 text-2xl leading-tight font-bold tracking-tight text-navy-900">{children}</h3>
  )
}

/** The numbers that matter, large enough to read without reading the text. */
function Facts({ facts }: { facts: Fact[] }) {
  return (
    <dl
      className="mt-4 grid gap-2"
      style={{ gridTemplateColumns: `repeat(${facts.length}, minmax(0, 1fr))` }}
    >
      {facts.map(({ label, value }) => (
        <div key={label} className="rounded-2xl bg-navy-50/70 px-4 py-3">
          <dt className="text-xs font-bold text-navy-500">{label}</dt>
          <dd className="mt-0.5 text-lg leading-tight font-bold whitespace-nowrap text-navy-900">
            {value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function Bullets({ items }: { items: string[] }) {
  if (items.length === 0) return null
  return (
    <ul className="mt-3 space-y-1.5">
      {items.map((text) => (
        <li key={text} className="flex gap-3">
          <span className="mt-[0.6em] size-1.5 shrink-0 rounded-full bg-navy-200" />
          <span>
            <Emphasis text={text} />
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Literal quotes: the guide first, the Labour Code behind a toggle so the details stay short. */
function Sources({ sources }: { sources: SourceRef[] }) {
  const guide = sources.filter((s) => s.doc === 'przewodnik')
  const law = sources.filter((s) => s.doc === 'kp')
  const [lawOpen, setLawOpen] = useState(guide.length === 0)
  if (sources.length === 0) return null
  return (
    <section className="mt-6 border-t border-line pt-5">
      <p className="text-sm font-bold text-navy-900">Źródło</p>
      <div className="mt-3 space-y-4">
        {guide.map((source) => (
          <Quote key={source.quote} source={source} />
        ))}
      </div>
      {law.length > 0 && (
        <div className={cn(guide.length > 0 && 'mt-4')}>
          <button
            type="button"
            onClick={() => setLawOpen((open) => !open)}
            aria-expanded={lawOpen}
            className="flex items-center gap-1.5 text-sm font-bold text-zus-700"
          >
            {law.length === 1 ? 'Przepis z Kodeksu pracy' : `Przepisy z Kodeksu pracy (${law.length})`}
            <ChevronDown
              className={cn('size-4 transition-transform duration-200', lawOpen && 'rotate-180')}
            />
          </button>
          <AnimatePresence initial={false}>
            {lawOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
                transition={{ duration: 0.22, ease: EASE_OUT }}
                className="overflow-hidden"
              >
                <div className="space-y-4 pt-3">
                  {law.map((source) => (
                    <Quote key={source.quote} source={source} />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </section>
  )
}

function Quote({ source }: { source: SourceRef }) {
  return (
    <figure>
      <blockquote className="text-navy-700">„{source.quote}”</blockquote>
      <figcaption className="mt-1 text-sm text-navy-400">{sourceLabel(source)}</figcaption>
    </figure>
  )
}
