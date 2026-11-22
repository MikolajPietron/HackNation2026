// Organisations and public services that support parents (the brief, point i; FUNKCJE F28).
// Calm on purpose: no badges, no colour alarms, the most practical line first. Shown in full in
// the "Wsparcie dla rodziców" window, and by topic where the plan needs it (after a loss, with a
// premature baby or a child in hospital).
import { ExternalLink } from 'lucide-react'
import { Illustration } from '@/components/ui/illustration'
import { formatLongDate } from '@/lib/dates'
import { CHECKED_ON, SUPPORT } from '@/lib/support'
import type { SupportTopic } from '@/lib/support'
import { cn } from '@/lib/utils'

export function SupportList({ topics, className }: { topics?: SupportTopic[]; className?: string }) {
  const groups = SUPPORT.filter((group) => !topics || topics.includes(group.topic))
  return (
    <div className={cn('space-y-6', className)}>
      {groups.map((group) => (
        <section key={group.topic}>
          <h3 className="flex items-center gap-2 font-bold text-navy-900">
            <Illustration src={group.icon} size="hint" />
            {group.title}
          </h3>
          <ul className="mt-2 space-y-2">
            {group.entries.map((entry) => (
              <li key={entry.name} className="rounded-2xl border border-line px-4 py-3">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <p className="font-bold text-navy-900">{entry.name}</p>
                  {entry.link && (
                    <a
                      href={entry.link.href}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 text-sm font-bold text-zus-700 underline-offset-4 hover:underline"
                    >
                      {entry.link.label}
                      <ExternalLink className="size-3.5" />
                    </a>
                  )}
                </div>
                <p className="mt-0.5 text-sm leading-relaxed text-navy-700">{entry.what}</p>
                {entry.where && <p className="mt-0.5 text-sm text-navy-500">{entry.where}</p>}
              </li>
            ))}
          </ul>
        </section>
      ))}
      <p className="text-xs text-navy-400">
        Sprawdzone {formatLongDate(CHECKED_ON)}. Aplikacja nie jest powiązana z tymi organizacjami;
        przed kontaktem sprawdź aktualne dane na ich stronach.
      </p>
    </div>
  )
}

/** The whole list in a window: "Wsparcie dla rodziców". */
export function SupportWindow() {
  return (
    <div className="text-navy-700">
      <header className="pr-10">
        <h2 className="text-2xl font-bold tracking-tight text-navy-900">Wsparcie dla rodziców</h2>
        <p className="mt-2">
          Gdzie szukać pomocy po stracie dziecka, przy wcześniaku, przy ciężko chorym dziecku i
          wtedy, gdy jest bardzo ciężko.
        </p>
      </header>
      <SupportList className="mt-6" />
    </div>
  )
}
