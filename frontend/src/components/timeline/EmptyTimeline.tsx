import { cn } from '@/lib/utils'

// Ghost pills that hint at the shape of the timeline: [offset %, width %, colour].
const GHOSTS = [
  [8, 52, 'bg-zus-200'],
  [38, 22, 'bg-zus-100'],
] as const

/** Before the birth date is known: one sentence and a quiet preview, nothing to read. */
export function EmptyTimeline() {
  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-black text-navy-900 lg:text-3xl">Twoja oś czasu</h1>
        <p className="mt-2 max-w-md text-navy-500">
          Podaj w rozmowie datę porodu. Pokażemy tu, od kiedy mama może zacząć urlop macierzyński i ile on trwa.
        </p>
      </div>
      <div className="space-y-3.5" aria-hidden>
        {GHOSTS.map(([left, width, color], index) => (
          <div key={index} className="relative h-11">
            <span
              className={cn('absolute inset-y-0 rounded-full motion-safe:animate-pulse', color)}
              style={{ left: `${left}%`, width: `${width}%`, animationDelay: `${index * 180}ms` }}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
