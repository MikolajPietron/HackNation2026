import { useMemo } from 'react'
import type { ChangeSet } from '../../hooks/useAssistant'
import { formatLongDate } from '../../lib/dates'
import type { Timeline } from '../../types'
import { AlertIcon } from '../Icons'
import { EmptyTimeline } from './EmptyTimeline'
import { HorizontalTimeline } from './HorizontalTimeline'
import { timelineItems } from './items'
import { VerticalTimeline } from './VerticalTimeline'

interface Props {
  timeline: Timeline | null
  changed: ChangeSet
  selectedId: string | null
  focus: { id: string | null; tick: number }
  onSelect: (id: string | null) => void
}

export function TimelinePanel({ timeline, changed, selectedId, focus, onSelect }: Props) {
  const items = useMemo(() => (timeline ? timelineItems(timeline) : []), [timeline])
  const changedIds = useMemo(() => new Set(changed.ids), [changed])

  if (!timeline) {
    return (
      <div className="p-4 sm:p-6">
        <EmptyTimeline />
      </div>
    )
  }

  const view = { timeline, items, selectedId, changedIds, changeVersion: changed.version, focus, onSelect }
  const children =
    timeline.children_count === 1 ? '1 dziecko' : `${timeline.children_count} dzieci z jednego porodu`

  return (
    <div className="space-y-5 p-4 @container sm:p-6">
      <header className="space-y-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="text-xl font-semibold text-stone-900">Twoja oś czasu</h2>
          <p className="text-xs text-stone-500">
            Liczy kalkulator reguł (bez AI) · parametry {timeline.params_version}
          </p>
        </div>
        <p className="text-sm text-stone-600">
          {timeline.child_born ? 'Data urodzenia' : 'Przewidywana data porodu'}:{' '}
          <strong className="text-stone-900">{formatLongDate(timeline.birth_date)}</strong> ·{' '}
          {children}
        </p>
      </header>

      {timeline.warnings.map((warning) => (
        <p
          key={warning}
          className="flex gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900 ring-1 ring-amber-200"
        >
          <AlertIcon className="mt-0.5 size-4 shrink-0" />
          {warning}
        </p>
      ))}

      <Legend />

      <div className="hidden @2xl:block">
        <HorizontalTimeline {...view} />
      </div>
      <div className="@2xl:hidden">
        <VerticalTimeline {...view} />
      </div>

      <details className="rounded-2xl bg-white p-4 text-sm text-stone-700 shadow-sm ring-1 ring-stone-200">
        <summary className="cursor-pointer font-medium text-stone-900">Założenia kalkulatora</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          {timeline.assumptions.map((assumption) => (
            <li key={assumption}>{assumption}</li>
          ))}
        </ul>
      </details>
    </div>
  )
}

function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-stone-600">
      <li className="flex items-center gap-1.5">
        <span className="h-3 w-5 rounded border border-stone-400 bg-stone-100" /> urlop i % podstawy
        zasiłku
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-3 w-5 rounded border border-dashed border-stone-400" /> przykładowy
        termin
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-2.5 rotate-45 rounded-[2px] bg-amber-500" /> ważny dzień
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-violet-500" /> wniosek
      </li>
    </ul>
  )
}
