// "Przykładowe sprawy": the brief's test of the demo (the jury uploads or picks one of ZUS's
// example cases and checks the insurance and the calculation). Pick a case S01–S86 or upload its
// PDF; AI transcribes the documents (marked as AI), the calculator checks the sickness insurance
// and computes the benefit, and the result is set against the decision of ZUS in the case.
// The case can then become the plan on the timeline.
import { useEffect, useRef, useState } from 'react'
import type { DragEvent, ReactNode } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Check, ChevronRight } from 'lucide-react'
import { assessCase, fetchCases, loadCaseIntoPlan, readCase, uploadCase } from '@/api'
import { MockModal } from '@/components/mocks/MockModal'
import { Illustration } from '@/components/ui/illustration'
import { useDragScroll } from '@/hooks/useDragScroll'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { currentSessionId } from '@/lib/session'
import { cn } from '@/lib/utils'
import type { CaseFacts, CaseList, CaseListItem, CaseResult, SessionStart } from '@/types'
import { CaseResultView } from './CaseResultView'

/** A picture per category of the catalogue (tools/zus-data). */
const CATEGORY_ICON: Record<string, string> = {
  Odmowa: ICONS.koperta,
  'Martwe urodzenie': ICONS.serce,
  'Adopcja / rodzina zastępcza': ICONS.przyjecie,
  'Zasiłek w wys. zas. macierzyńskiego': ICONS.karton,
  'Wcześniak / uzupełniający': ICONS.inkubator,
  'Bliźnięta / Za życiem': ICONS.blizniaki,
  'Łączenie rodzicielskiego z pracą': ICONS.etat,
  'Ojciec: 9 tyg. / przejęcie': ICONS.tataZDzieckiem,
  'Urlop ojcowski': ICONS.tataZDzieckiem,
  'Chorobowy w ciąży': ICONS.zaswiadczenie,
  'Macierzyński + rodzicielski': ICONS.wozek,
  Macierzyński: ICONS.mamaZDzieckiem,
}
const iconOf = (category: string) => CATEGORY_ICON[category] ?? ICONS.kalendarz

type View =
  | { kind: 'pick' }
  | { kind: 'reading'; label: string; pages: number | null; started: number }
  | { kind: 'result'; result: CaseResult; category: string | null }

export function CasesDialog({
  open,
  onClose,
  onLoaded,
}: {
  open: boolean
  onClose: () => void
  /** The case became the plan. */
  onLoaded: (start: SessionStart) => void
}) {
  const [view, setView] = useState<View>({ kind: 'pick' })
  const [list, setList] = useState<CaseList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const request = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!open) return
    fetchCases()
      .then(setList)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Nie udało się wczytać spraw.'))
  }, [open, view.kind])

  const close = () => {
    request.current?.abort()
    onClose()
  }

  const run = async (label: string, pages: number | null, category: string | null, read: (signal: AbortSignal) => Promise<CaseResult>) => {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setError(null)
    setView({ kind: 'reading', label, pages, started: Date.now() })
    try {
      const result = await read(controller.signal)
      setView({ kind: 'result', result, category })
    } catch (e) {
      if (controller.signal.aborted) return
      setError(e instanceof Error ? e.message : 'Nie udało się odczytać sprawy.')
      setView({ kind: 'pick' })
    }
  }

  const pick = (item: CaseListItem) =>
    run(`Czytam sprawę ${item.id}`, item.pages, item.category, (signal) => readCase(item.id, signal))
  const upload = (file: File) =>
    run('Czytam wgrany plik', null, null, (signal) => uploadCase(file, signal))

  const recalculate = async (result: CaseResult, category: string | null, facts: CaseFacts) => {
    setBusy(true)
    setError(null)
    try {
      const next = await assessCase({ id: result.id, pages: result.pages, pages_read: result.pages_read, facts })
      setView({ kind: 'result', result: next, category })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nie udało się przeliczyć.')
    } finally {
      setBusy(false)
    }
  }

  const showPlan = async (result: CaseResult) => {
    setBusy(true)
    setError(null)
    try {
      const start = await loadCaseIntoPlan(currentSessionId(), result.scenario)
      onLoaded(start)
      onClose()
      setView({ kind: 'pick' })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nie udało się wczytać sprawy do planu.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <MockModal open={open} label="Przykładowe sprawy" onClose={close} className="max-w-4xl">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={view.kind}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6, transition: { duration: 0.12 } }}
          transition={{ duration: 0.22, ease: EASE_OUT }}
        >
          {view.kind === 'pick' && (
            <Picker list={list} error={error} onPick={pick} onUpload={upload} />
          )}
          {view.kind === 'reading' && (
            <Reading
              label={view.label}
              pages={view.pages}
              started={view.started}
              onCancel={() => {
                request.current?.abort()
                setView({ kind: 'pick' })
              }}
            />
          )}
          {view.kind === 'result' && (
            <CaseResultView
              result={view.result}
              category={view.category}
              busy={busy}
              error={error}
              onBack={() => {
                setError(null)
                setView({ kind: 'pick' })
              }}
              onRecalculate={(facts) => recalculate(view.result, view.category, facts)}
              onShowPlan={() => showPlan(view.result)}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </MockModal>
  )
}

function Picker({
  list,
  error,
  onPick,
  onUpload,
}: {
  list: CaseList | null
  error: string | null
  onPick: (item: CaseListItem) => void
  onUpload: (file: File) => void
}) {
  const [filter, setFilter] = useState<string | null>(null)
  const chips = useDragScroll<HTMLDivElement>()
  const cases = list?.cases ?? []
  const categories = [...new Set(cases.map((c) => c.category))]
  const shown = filter ? cases.filter((c) => c.category === filter) : cases

  return (
    <div>
      <header className="pr-10">
        <h2 className="text-2xl leading-tight font-bold tracking-tight text-navy-900">
          Sprawdź na przykładowej sprawie
        </h2>
        <p className="mt-1 text-pretty text-navy-500">
          Wybierz sprawę z zestawu ZUS albo wgraj jej PDF. AI przepisze dane z dokumentów,
          kalkulator sprawdzi ubezpieczenie i policzy zasiłek, a na końcu porównamy wynik z
          decyzją ZUS.
        </p>
      </header>

      <a
        href="/raport"
        className="mt-3 inline-flex items-center gap-1 text-sm font-bold text-zus-700 underline-offset-4 hover:underline"
      >
        Raport zgodności z decyzjami ZUS <ChevronRight className="size-4" />
      </a>

      <UploadZone onFile={onUpload} />

      {error && <p className="mt-4 rounded-2xl bg-alert-50 px-4 py-3 text-sm text-alert-600">{error}</p>}

      {list && !list.configured && (
        <p className="mt-4 rounded-2xl bg-sun-100 px-4 py-3 text-sm text-sun-700">
          Na serwerze nie ma folderu ze sprawami (CASES_DIR). Wgraj PDF sprawy powyżej.
        </p>
      )}

      {cases.length > 0 && (
        <>
          <div
            ref={chips}
            className="scrollbar-none -mx-6 mt-6 flex gap-2 overflow-x-auto px-6 sm:-mx-8 sm:px-8"
          >
            <Chip active={filter === null} onClick={() => setFilter(null)}>
              Wszystkie · {cases.length}
            </Chip>
            {categories.map((category) => (
              <Chip key={category} active={filter === category} onClick={() => setFilter(category)}>
                <Illustration src={iconOf(category)} size="hint" />
                {category} · {cases.filter((c) => c.category === category).length}
              </Chip>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-1 gap-2 min-[480px]:grid-cols-2 lg:grid-cols-3">
            {shown.map((item) => {
              return (
                <motion.button
                  key={item.id}
                  type="button"
                  onClick={() => onPick(item)}
                  whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
                  className="group flex items-start gap-3 rounded-2xl border border-line p-3 text-left transition-[border-color,background-color] duration-200 hover:border-navy-200 hover:bg-navy-50/40 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
                >
                  <Illustration src={iconOf(item.category)} size="event" className="bg-navy-50/60" />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2 text-xs font-black text-navy-400">
                      {item.id}
                      <span className="font-bold">· {item.pages} str.</span>
                      {item.read && (
                        <span className="ml-auto flex items-center gap-1 rounded-full bg-zus-50 px-1.5 py-0.5 text-[10px] font-bold text-zus-700">
                          <Check className="size-3" strokeWidth={3} /> odczytana
                        </span>
                      )}
                    </span>
                    <span className="mt-0.5 block leading-snug font-bold text-navy-900">
                      {item.title || item.category}
                    </span>
                    {item.title && (
                      <span className="block text-sm leading-snug text-navy-500">{item.category}</span>
                    )}
                  </span>
                </motion.button>
              )
            })}
          </div>
        </>
      )}
      {!list && !error && (
        <div className="mt-6 grid grid-cols-1 gap-2 min-[480px]:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="h-[76px] animate-pulse rounded-2xl bg-navy-50" />
          ))}
        </div>
      )}
    </div>
  )
}

/** Drop or pick a PDF or a photo; read by AI (marked). The cases and the letters from ZUS. */
export function UploadZone({
  onFile,
  title = 'Wgraj sprawę (PDF albo zdjęcie)',
  hint = 'Przeciągnij plik albo kliknij. ZAM, Z-3, poświadczenia, decyzje: wszystkie strony naraz.',
  icon = ICONS.zaswiadczenie,
}: {
  onFile: (file: File) => void
  title?: string
  hint?: string
  icon?: string
}) {
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const drop = (event: DragEvent) => {
    event.preventDefault()
    setOver(false)
    const file = event.dataTransfer.files[0]
    if (file) onFile(file)
  }
  return (
    <button
      type="button"
      onClick={() => input.current?.click()}
      onDragOver={(event) => {
        event.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
      className={cn(
        'group mt-5 flex w-full items-center gap-4 rounded-3xl border-2 border-dashed px-4 py-4 text-left transition-[border-color,background-color] duration-200 sm:px-5',
        over ? 'border-zus-400 bg-zus-50' : 'border-navy-200 hover:border-zus-400 hover:bg-zus-50/50',
      )}
    >
      <span className="transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:-translate-y-0.5">
        <Illustration src={icon} size="lane" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-bold text-navy-900">{title}</span>
        <span className="block text-sm text-navy-500">{hint}</span>
      </span>
      <span className="rounded-full bg-zus-600 px-2 py-0.5 text-[10px] font-black tracking-wide text-white">AI</span>
      <input
        ref={input}
        type="file"
        accept="application/pdf,image/jpeg,image/png"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) onFile(file)
        }}
      />
    </button>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3 text-sm font-bold whitespace-nowrap transition-colors duration-150',
        active ? 'border-navy-900 bg-navy-900 text-white' : 'border-line bg-white text-navy-700 hover:border-navy-200',
      )}
    >
      {children}
    </button>
  )
}

/** While AI reads the scans: a page with a line moving over it, the time it takes, and a way out. */
export function Reading({
  label,
  pages,
  started,
  onCancel,
  what = 'AI przepisuje dane z dokumentów',
  note = 'Pierwszy odczyt trwa zwykle kilkanaście sekund. Potem sprawa jest w pamięci serwera i otwiera się od razu.',
  icon = ICONS.zaswiadczenie,
}: {
  label: string
  pages: number | null
  started: number
  onCancel: () => void
  what?: string
  note?: string
  icon?: string
}) {
  const reduce = useReducedMotion()
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(id)
  }, [])
  const seconds = Math.max(0, Math.floor((now - started) / 1000))
  return (
    <div className="flex flex-col items-center py-8 text-center" aria-live="polite">
      <div className="relative grid size-32 place-items-center overflow-hidden rounded-[32px] bg-navy-50">
        <Illustration src={icon} size="lane" className="scale-150" />
        {!reduce && (
          <motion.span
            className="absolute inset-x-4 h-0.5 rounded-full bg-zus-400 shadow-[0_0_12px_2px_var(--color-zus-300)]"
            initial={{ top: '18%' }}
            animate={{ top: ['18%', '82%', '18%'] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
      </div>
      <h2 className="mt-6 text-2xl font-bold tracking-tight text-navy-900">{label}</h2>
      <p className="mt-1 text-navy-500">
        {pages ? `${pages} stron · ` : ''}{what}
        <span className="ml-2 rounded-full bg-zus-600 px-2 py-0.5 align-middle text-[10px] font-black tracking-wide text-white">
          AI
        </span>
      </p>
      <p className="mt-4 text-3xl font-bold text-navy-900 tabular-nums">
        {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}
      </p>
      <p className="mt-2 max-w-sm text-sm text-pretty text-navy-500">{note}</p>
      <button
        type="button"
        onClick={onCancel}
        className="mt-6 h-10 rounded-full px-4 text-sm font-bold text-navy-500 transition-colors hover:bg-navy-50 hover:text-navy-900"
      >
        Przerwij
      </button>
    </div>
  )
}
