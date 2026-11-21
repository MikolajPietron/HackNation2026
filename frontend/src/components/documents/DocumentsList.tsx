import { Check, FileText } from 'lucide-react'
import { NavListCard } from '@/components/ui/nav-list-card'
import { formatDate } from '@/lib/dates'
import type { Timeline } from '@/types'

/** Documents the parent needs, with the day they are needed. */
export function DocumentsList({
  timeline,
  selectedId,
  onSelect,
  className,
}: {
  timeline: Timeline
  selectedId: string | null
  onSelect: (id: string) => void
  className?: string
}) {
  return (
    <NavListCard
      title="Dokumenty"
      className={className}
      items={timeline.documents.map((d) => ({
        id: d.id,
        icon: d.done ? <Check /> : <FileText />,
        iconClassName: d.done ? 'bg-zus-100 text-zus-700' : 'bg-sun-100 text-sun-700',
        label: d.label,
        meta: d.done ? 'mama już je ma' : `potrzebne na ${formatDate(d.needed_by)}`,
        selected: d.id === selectedId,
        onSelect: () => onSelect(d.id),
      }))}
    />
  )
}
