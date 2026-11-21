import { cx, LANE, LANES } from '../../lib/ui'

// Placeholder bars: [offset %, width %] per lane, only to hint at the shape of the timeline.
const SKETCH = {
  mother: [[6, 34], [41, 46]],
  father: [[6, 4], [88, 10]],
  child: [[6, 1], [12, 1], [70, 1]],
  applications: [[3, 1], [33, 1], [80, 1]],
} as const

const PROMISES = [
  ['Urlopy mamy i taty', 'Od kiedy do kiedy, ile tygodni i jaki procent podstawy zasiłku.'],
  ['Wnioski i terminy', 'Co złożyć, gdzie i do którego dnia — z przypomnieniem o terminach.'],
  ['Źródła z cytatami', 'Każdy element osi ma zasadę z Przewodnika ZUS albo przepisu.'],
] as const

export function EmptyTimeline() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-stone-900">Twoja oś czasu</h2>
        <p className="mt-1 text-sm text-stone-600">
          Pojawi się tutaj, gdy w rozmowie podasz datę porodu — faktyczną albo przewidywaną.
        </p>
      </div>
      <div className="overflow-hidden rounded-2xl border border-dashed border-stone-300 bg-white/70">
        {LANES.map((lane) => (
          <div
            key={lane}
            className="flex items-center gap-3 border-b border-dashed border-stone-200 px-4 py-4 last:border-b-0"
          >
            <span className="flex w-36 shrink-0 items-center gap-2 text-sm font-medium text-stone-500">
              <span className={cx('size-2 rounded-full opacity-60', LANE[lane].dot)} />
              {LANE[lane].label}
            </span>
            <div className="relative h-5 flex-1">
              {SKETCH[lane].map(([left, width]) => (
                <span
                  key={left}
                  className="absolute inset-y-0 rounded-md bg-stone-100 motion-safe:animate-pulse"
                  style={{ left: `${left}%`, width: `${width}%`, minWidth: 10 }}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
      <ul className="grid gap-3 sm:grid-cols-3">
        {PROMISES.map(([title, text]) => (
          <li key={title} className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-stone-200">
            <p className="font-semibold text-stone-900">{title}</p>
            <p className="mt-1 text-sm text-stone-600">{text}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
