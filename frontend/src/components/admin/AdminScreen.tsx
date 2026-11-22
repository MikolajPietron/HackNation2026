// Admin panel (FUNKCJE F36, the brief: parameters changed in an admin panel when the law
// changes). Every number the engine uses, with its source; a change is saved as a new version
// valid from a date, and the panel shows what it does to an example family's plan before saving.
// Demo: no sign-in. Same visual language and motion as the parents' app (Emil Kowalski's rules,
// Spectrum UI's TextStates, our calendar and illustrations).
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, CalendarDays, ChevronDown, Minus, Plus, RotateCcw } from 'lucide-react'
import { fetchAdminParams, previewParams, saveParamVersion } from '@/api'
import { Brand } from '@/components/layout/Brand'
import { SimBadge } from '@/components/mocks/MockModal'
import { Calendar } from '@/components/onboarding/Calendar'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import { ITEM, STEP } from '@/components/onboarding/motion'
import { Illustration } from '@/components/ui/illustration'
import { TextStates } from '@/components/ui/text-states'
import { addDaysIso, dayNumber, formatShortDate } from '@/lib/dates'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { formatPln, formatRate } from '@/lib/money'
import { sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { AdminView, Param, ParamPreview, ParamValues, ParamVersion, Params, SourceRef, Timeline } from '@/types'

const CHILDREN = ['1 dziecko', 'Bliźnięta', 'Trojaczki', 'Czworaczki', '5 i więcej']
const CHILDREN_ICON = [ICONS.mamaZDzieckiem, ICONS.blizniaki, ICONS.trojaczki, ICONS.trojaczki, ICONS.trojaczki]

type NumberKey = {
  [K in keyof ParamValues]: ParamValues[K] extends number ? K : never
}[keyof ParamValues]

/** One number of the panel besides the weeks of maternity leave: where it lives in the base file
 *  (for its sources) and how the panel names it. */
interface NumberField {
  key: NumberKey
  param: (base: Params) => Param<number>
  icon: string
  label: string
  hint: string
}

/** Guide section G: percent of the benefit base. */
const RATES: NumberField[] = [
  {
    key: 'rate_full',
    param: (p) => p.money.rate_full,
    icon: ICONS.mamaZDzieckiem,
    label: 'Urlop macierzyński, uzupełniający i ojcowski',
    hint: 'Także urlop na warunkach urlopu macierzyńskiego',
  },
  {
    key: 'rate_parental',
    param: (p) => p.money.rate_parental,
    icon: ICONS.wozek,
    label: 'Urlop rodzicielski',
    hint: 'Gdy mama nie złoży wniosku o jedną stawkę; za 9 tygodni drugiego rodzica zawsze',
  },
  {
    key: 'rate_single',
    param: (p) => p.money.rate_single,
    icon: ICONS.skarbonka,
    label: 'Jedna stawka na wniosek mamy',
    hint: 'Za urlop macierzyński i rodzicielski, poza 9 tygodniami drugiego rodzica',
  },
]

/** The key deadlines of the requests, in days. */
const DEADLINES: NumberField[] = [
  {
    key: 'rate_single_request_days',
    param: (p) => p.money.request_days,
    icon: ICONS.skarbonka,
    label: 'Wniosek o jedną stawkę',
    hint: 'Najpóźniej tyle dni po porodzie',
  },
  {
    key: 'parental_request_days',
    param: (p) => p.applications.parental_days_before,
    icon: ICONS.wozek,
    label: 'Wniosek o urlop rodzicielski',
    hint: 'Co najmniej tyle dni przed jego rozpoczęciem',
  },
  {
    key: 'paternity_request_days',
    param: (p) => p.applications.paternity_days_before,
    icon: ICONS.tataZDzieckiem,
    label: 'Wniosek o urlop ojcowski',
    hint: 'Co najmniej tyle dni przed jego rozpoczęciem',
  },
  {
    key: 'supplementary_request_days',
    param: (p) => p.applications.supplementary_days_before_end,
    icon: ICONS.inkubator,
    label: 'Wniosek o urlop uzupełniający',
    hint: 'Co najmniej tyle dni przed końcem urlopu macierzyńskiego',
  },
]

/** 81.5 -> "81,5" */
const decimal = (value: number) => String(value).replace('.', ',')

const RULES: Record<string, string> = {
  medical_certificate: 'Urlop przed porodem wymaga zaświadczenia lekarskiego o przewidywanej dacie porodu',
  work_until_birth: 'Mama może pracować do dnia porodu',
  week_is_7_days: 'Tydzień urlopu to 7 dni kalendarzowych',
  first_day_is_birth: 'Bez urlopu przed porodem urlop zaczyna się w dniu porodu',
  rest_after_birth: 'Część niewykorzystana przed porodem przechodzi na czas po porodzie',
}

const STATUS: Record<ParamVersion['status'], { label: string; className: string }> = {
  in_force: { label: 'Obowiązuje', className: 'bg-zus-50 text-zus-700' },
  scheduled: { label: 'Zaplanowana', className: 'bg-sun-100 text-sun-700' },
  past: { label: 'Archiwalna', className: 'bg-navy-50 text-navy-500' },
}

const same = (a: ParamValues, b: ParamValues) => JSON.stringify(a) === JSON.stringify(b)

export function AdminScreen() {
  const [view, setView] = useState<AdminView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<ParamValues | null>(null)
  const [toast, setToast] = useState<{ text: string; id: number } | null>(null)

  useEffect(() => {
    fetchAdminParams()
      .then((v) => {
        setView(v)
        setDraft(v.in_force)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Nie udało się wczytać parametrów.'))
  }, [])

  useEffect(() => {
    if (!toast) return
    const id = window.setTimeout(() => setToast(null), 3600)
    return () => window.clearTimeout(id)
  }, [toast])

  return (
    <div className="min-h-dvh bg-white">
      <header className="sticky top-0 z-30 flex h-[72px] items-center gap-4 border-b border-line bg-white/90 px-4 backdrop-blur lg:px-6">
        <Brand className="hidden sm:flex" />
        <span className="hidden h-8 w-px bg-line sm:block" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-lg font-bold text-navy-900">Panel parametrów</p>
          <p className="truncate text-xs text-navy-500">Liczby, z których liczy silnik reguł</p>
        </div>
        <span className="hidden md:inline-flex">
          <SimBadge>demo · bez logowania</SimBadge>
        </span>
        <a
          href="/"
          className="flex h-10 items-center gap-1.5 rounded-full px-3 text-sm font-bold text-navy-500 transition-[background-color,color] duration-150 hover:bg-navy-50 hover:text-navy-900"
        >
          <ArrowLeft className="size-4" /> <span className="hidden sm:inline">Wróć do aplikacji</span>
        </a>
      </header>

      {error && (
        <p className="mx-auto mt-10 max-w-xl rounded-3xl bg-alert-50 px-5 py-4 text-alert-600">{error}</p>
      )}
      {!view && !error && <Loading />}
      {view && draft && (
        <motion.main
          variants={STEP}
          initial="enter"
          animate="center"
          className="mx-auto grid max-w-[1280px] gap-8 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_400px] lg:px-8 lg:py-8"
        >
          <div className="min-w-0 space-y-5">
            <motion.div variants={ITEM}>
              <h1 className="text-3xl font-bold tracking-tight text-navy-900 lg:text-4xl">Urlopy, stawki i terminy</h1>
              <p className="mt-1 max-w-2xl text-navy-500">
                Zmiana to nowa wersja od wybranej daty. Do tego dnia silnik liczy po obecnych
                zasadach. Wersja bazowa: {view.base.version}.
              </p>
            </motion.div>

            <ParamCard
              icon={ICONS.mamaZDzieckiem}
              title="Wymiar urlopu macierzyńskiego"
              hint="Tygodnie według liczby dzieci urodzonych przy jednym porodzie"
            >
              {draft.weeks_by_children.map((weeks, index) => (
                <Row key={CHILDREN[index]} icon={CHILDREN_ICON[index]} label={CHILDREN[index]}>
                  <Stepper
                    value={weeks}
                    base={view.in_force.weeks_by_children[index]}
                    label={`Tygodnie urlopu — ${CHILDREN[index]}`}
                    onChange={(value) => {
                      const next = [...draft.weeks_by_children]
                      next[index] = value
                      setDraft({ ...draft, weeks_by_children: next })
                    }}
                  />
                </Row>
              ))}
              <Sources sources={view.base.maternity.weeks_by_children.sources} className="mt-3" />
            </ParamCard>

            <ParamCard
              icon={ICONS.kalendarz}
              title="Przed porodem i po porodzie"
              hint="Jak urlop dzieli się wokół porodu"
            >
              <Row
                icon={ICONS.odpoczynek}
                label="Najwięcej przed porodem"
                hint="Tygodnie przed przewidywaną datą porodu"
                sources={view.base.maternity.max_weeks_before_birth.sources}
              >
                <Stepper
                  value={draft.max_weeks_before_birth}
                  base={view.in_force.max_weeks_before_birth}
                  label="Tygodnie przed porodem"
                  min={0}
                  onChange={(value) => setDraft({ ...draft, max_weeks_before_birth: value })}
                />
              </Row>
              <Row
                icon={ICONS.klepsydra}
                label="Tylko dla mamy po porodzie"
                hint="Tygodnie, których mama nie może oddać"
                sources={view.base.maternity.mother_personal_weeks.sources}
              >
                <Stepper
                  value={draft.mother_personal_weeks}
                  base={view.in_force.mother_personal_weeks}
                  label="Tygodnie tylko dla mamy"
                  onChange={(value) => setDraft({ ...draft, mother_personal_weeks: value })}
                />
              </Row>
            </ParamCard>

            <ParamCard
              icon={ICONS.pieniadze}
              title="Wysokość zasiłku macierzyńskiego"
              hint="Procent podstawy wymiaru zasiłku"
            >
              {RATES.map((field) => (
                <Row
                  key={field.key}
                  icon={field.icon}
                  label={field.label}
                  hint={field.hint}
                  sources={field.param(view.base).sources}
                >
                  <Stepper
                    value={draft[field.key]}
                    base={view.in_force[field.key]}
                    label={field.label}
                    unit="%"
                    step={0.5}
                    min={0.5}
                    max={100}
                    format={decimal}
                    wide
                    onChange={(value) => setDraft({ ...draft, [field.key]: value })}
                  />
                </Row>
              ))}
            </ParamCard>

            <ParamCard icon={ICONS.koperta} title="Terminy wniosków" hint="Liczba dni kalendarzowych">
              {DEADLINES.map((field) => (
                <Row
                  key={field.key}
                  icon={field.icon}
                  label={field.label}
                  hint={field.hint}
                  sources={field.param(view.base).sources}
                >
                  <Stepper
                    value={draft[field.key]}
                    base={view.in_force[field.key]}
                    label={field.label}
                    unit="dni"
                    max={90}
                    onChange={(value) => setDraft({ ...draft, [field.key]: value })}
                  />
                </Row>
              ))}
            </ParamCard>

            <motion.section variants={ITEM} className="rounded-3xl border border-line p-5">
              <h2 className="font-bold text-navy-900">Reguły bez liczb</h2>
              <p className="mt-0.5 text-sm text-navy-500">Zmiana reguły wymaga zmiany silnika, nie tylko parametru.</p>
              <ul className="mt-3 divide-y divide-line">
                {Object.entries(view.base.rules).map(([id, rule]) => (
                  <li key={id} className="py-3">
                    <p className="font-bold text-navy-900">{RULES[id] ?? id}</p>
                    <Sources sources={rule.sources} className="mt-2" />
                  </li>
                ))}
              </ul>
            </motion.section>
          </div>

          <aside className="lg:sticky lg:top-[96px] lg:self-start">
            <NewVersion
              view={view}
              draft={draft}
              onReset={() => setDraft(view.in_force)}
              onSaved={(next, effective) => {
                setView(next)
                setDraft(next.in_force)
                const future = effective > next.today
                setToast({
                  id: Date.now(),
                  text: future
                    ? `Zapisano. Wersja zacznie obowiązywać ${formatShortDate(effective)}.`
                    : 'Zapisano. Nowa wersja już obowiązuje w kalkulatorze.',
                })
              }}
            />
            <History view={view} />
          </aside>
        </motion.main>
      )}

      <AnimatePresence>
        {toast && (
          <motion.div
            key={toast.id}
            role="status"
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, transition: { duration: 0.15 } }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            className="fixed inset-x-4 bottom-6 z-50 rounded-3xl bg-navy-900 px-5 py-3 text-sm font-bold text-white shadow-[0_18px_40px_-18px_rgb(26_36_56/0.6)] sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2 sm:rounded-full"
          >
            {toast.text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function ParamCard({
  icon,
  title,
  hint,
  children,
}: {
  icon: string
  title: string
  hint: string
  children: ReactNode
}) {
  return (
    <motion.section variants={ITEM} className="rounded-3xl border border-line p-5">
      <div className="flex items-start gap-3">
        <Illustration src={icon} size="event" className="bg-navy-50/60" />
        <div className="min-w-0 flex-1">
          <h2 className="font-bold text-navy-900">{title}</h2>
          <p className="text-sm text-navy-500">{hint}</p>
        </div>
      </div>
      <div className="mt-2 divide-y divide-line">{children}</div>
    </motion.section>
  )
}

/** One number: what it is (and its sources) on the left, the stepper on the right. */
function Row({
  icon,
  label,
  hint,
  sources,
  children,
}: {
  icon: string
  label: string
  hint?: string
  sources?: SourceRef[]
  children: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3">
      <Illustration src={icon} size="hint" />
      <div className="min-w-0 flex-1">
        <p className="font-bold text-navy-900">{label}</p>
        {hint && <p className="text-sm text-navy-500">{hint}</p>}
        {sources && <Sources sources={sources} className="mt-2" />}
      </div>
      <div className="ml-auto">{children}</div>
    </div>
  )
}

/** −/+ with the number swapping in place. A changed value shows what it was, to its left, so
 *  the stepper itself never moves. */
function Stepper({
  value,
  base,
  label,
  unit = 'tyg.',
  step = 1,
  min = 1,
  max = 60,
  format = String,
  wide = false,
  onChange,
}: {
  value: number
  base: number
  label: string
  unit?: string
  step?: number
  min?: number
  max?: number
  format?: (value: number) => string
  /** Room for a decimal number ("81,5"), so the buttons stay put. */
  wide?: boolean
  onChange: (value: number) => void
}) {
  const changed = value !== base
  return (
    <div className="flex items-center gap-2" role="group" aria-label={label}>
      <AnimatePresence>
        {changed && (
          <motion.button
            type="button"
            onClick={() => onChange(base)}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.12 } }}
            transition={{ duration: 0.2, ease: EASE_OUT }}
            title="Przywróć"
            className="flex items-center gap-1 rounded-full bg-sun-100 px-2 py-0.5 text-xs font-bold whitespace-nowrap text-sun-700 transition-colors hover:bg-sun-300/60"
          >
            było {format(base)} <RotateCcw className="size-3" />
          </motion.button>
        )}
      </AnimatePresence>
      <StepButton label="Mniej" disabled={value - step < min} onClick={() => onChange(value - step)}>
        <Minus className="size-4" />
      </StepButton>
      <span
        className={cn(
          'text-center text-2xl font-bold tabular-nums transition-colors duration-200',
          wide ? 'w-14' : 'w-9',
          changed ? 'text-sun-700' : 'text-navy-900',
        )}
        aria-live="polite"
      >
        <TextStates text={format(value)} />
      </span>
      <StepButton label="Więcej" disabled={value + step > max} onClick={() => onChange(value + step)}>
        <Plus className="size-4" />
      </StepButton>
      <span className="w-7 text-sm font-bold text-navy-500">{unit}</span>
    </div>
  )
}

function StepButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string
  disabled: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <motion.button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      whileTap={disabled ? undefined : { scale: 0.9, transition: SPRING_PRESS }}
      className="grid size-9 place-items-center rounded-full border border-line bg-white text-navy-700 transition-[border-color,background-color,opacity] duration-150 hover:border-navy-200 hover:bg-navy-50 disabled:pointer-events-none disabled:opacity-30 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
    >
      {children}
    </motion.button>
  )
}

/** Source pills; one tap shows the literal quote under them. */
function Sources({ sources, className }: { sources: SourceRef[]; className?: string }) {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <div className={className}>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source, index) => (
          <button
            key={source.quote}
            type="button"
            onClick={() => setOpen(open === index ? null : index)}
            aria-expanded={open === index}
            className={cn(
              'rounded-full px-2.5 py-1 text-xs font-bold transition-colors duration-150',
              open === index ? 'bg-navy-900 text-white' : 'bg-navy-50 text-navy-500 hover:text-navy-900',
            )}
          >
            {sourceLabel(source)}
          </button>
        ))}
      </div>
      <AnimatePresence initial={false}>
        {open !== null && sources[open] && (
          <motion.blockquote
            key={open}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0, transition: { duration: 0.12 } }}
            transition={{ duration: 0.22, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <p className="pt-2 text-sm leading-relaxed text-navy-700">„{sources[open].quote}”</p>
          </motion.blockquote>
        )}
      </AnimatePresence>
    </div>
  )
}

function NewVersion({
  view,
  draft,
  onReset,
  onSaved,
}: {
  view: AdminView
  draft: ParamValues
  onReset: () => void
  onSaved: (view: AdminView, effective: string) => void
}) {
  const [effective, setEffective] = useState(view.today)
  const [calendar, setCalendar] = useState(false)
  const [note, setNote] = useState('')
  const [children, setChildren] = useState(1)
  const [rate815, setRate815] = useState(false)
  const [preview, setPreview] = useState<ParamPreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const dirty = !same(draft, view.in_force)

  // Preview what the draft does, a moment after the last change.
  useEffect(() => {
    const controller = new AbortController()
    const id = window.setTimeout(() => {
      previewParams(draft, children, rate815, controller.signal)
        .then((p) => {
          setPreview(p)
          setError(null)
        })
        .catch((e: unknown) => {
          if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Błąd podglądu.')
        })
    }, 250)
    return () => {
      window.clearTimeout(id)
      controller.abort()
    }
  }, [draft, children, rate815])

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const next = await saveParamVersion({ effective_from: effective, note, values: draft })
      setNote('')
      onSaved(next, effective)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nie udało się zapisać.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <motion.section variants={ITEM} className="rounded-3xl border border-line p-5">
      <div className="flex items-center gap-2">
        <h2 className="flex-1 text-lg font-bold text-navy-900">Nowa wersja</h2>
        <AnimatePresence>
          {dirty && (
            <motion.button
              type="button"
              onClick={onReset}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-sm font-bold text-navy-500 hover:text-navy-900"
            >
              Odrzuć zmiany
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      <p className="mt-4 text-sm font-bold text-navy-700">Obowiązuje od</p>
      <button
        type="button"
        onClick={() => setCalendar(!calendar)}
        aria-expanded={calendar}
        className="mt-1.5 flex h-11 w-full items-center gap-2 rounded-2xl border border-line px-4 text-left font-bold text-navy-900 transition-[border-color] duration-150 hover:border-navy-200"
      >
        <CalendarDays className="size-4 text-navy-400" />
        <span className="flex-1">
          {formatShortDate(effective)}
          {effective === view.today && <span className="font-normal text-navy-500"> · dziś</span>}
        </span>
        <ChevronDown className={cn('size-4 text-navy-400 transition-transform duration-200', calendar && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {calendar && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <div className="pt-2">
              <Calendar
                value={effective}
                min={view.today}
                max={addDaysIso(view.today, 3 * 366)}
                today={view.today}
                label="Obowiązuje od"
                onChange={(date) => {
                  setEffective(date)
                  setCalendar(false)
                }}
                className="[--cell:2.6rem]"
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <label className="mt-4 block text-sm font-bold text-navy-700" htmlFor="change-note">
        Podstawa zmiany
      </label>
      <textarea
        id="change-note"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        placeholder="np. nowelizacja Kodeksu pracy, art. 180 § 1"
        className="mt-1.5 w-full resize-none rounded-2xl border border-line px-4 py-3 text-navy-900 outline-none placeholder:text-navy-400 focus:border-zus-400 focus:ring-4 focus:ring-zus-600/10"
      />

      <div className="mt-5 flex items-center gap-2">
        <p className="flex-1 text-sm font-bold text-navy-700">Co się zmieni</p>
        <Segmented
          id="preview-children"
          options={['1 dziecko', 'bliźnięta', 'trojaczki']}
          selected={children - 1}
          onSelect={(index) => setChildren(index + 1)}
        />
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <p className="flex-1 text-xs text-navy-500">Przykładowa rodzina: mama i tata na etacie</p>
        <Segmented
          id="preview-rate"
          options={['100% i 70%', 'jedna stawka']}
          selected={rate815 ? 1 : 0}
          onSelect={(index) => setRate815(index === 1)}
        />
      </div>
      <PreviewDiff preview={preview} dirty={dirty} />

      {error && <p className="mt-3 rounded-2xl bg-alert-50 px-4 py-2.5 text-sm text-alert-600">{error}</p>}

      <PrimaryButton
        onClick={save}
        disabled={!dirty || note.trim().length < 3 || saving}
        className="mt-5 h-12 w-full text-base"
      >
        {saving ? 'Zapisuję…' : 'Zapisz nową wersję'}
      </PrimaryButton>
      {dirty && note.trim().length < 3 && (
        <p className="mt-2 text-center text-xs text-navy-500">Podaj podstawę zmiany, żeby zapisać.</p>
      )}
    </motion.section>
  )
}

/** A small pill switch for the preview's example family; the white pill slides to the choice. */
function Segmented({
  id,
  options,
  selected,
  onSelect,
}: {
  id: string
  options: string[]
  selected: number
  onSelect: (index: number) => void
}) {
  return (
    <div className="flex rounded-full bg-navy-50 p-0.5">
      {options.map((option, index) => (
        <button
          key={option}
          type="button"
          onClick={() => onSelect(index)}
          aria-pressed={selected === index}
          className={cn(
            'relative rounded-full px-2.5 py-1 text-xs font-bold whitespace-nowrap transition-colors',
            selected === index ? 'text-navy-900' : 'text-navy-500',
          )}
        >
          {selected === index && (
            <motion.span
              layoutId={id}
              className="absolute inset-0 rounded-full bg-white shadow-sm"
              transition={{ type: 'spring', duration: 0.3, bounce: 0.15 }}
            />
          )}
          <span className="relative">{option}</span>
        </button>
      ))}
    </div>
  )
}

interface Part {
  label: string
  before: string
  after: string
}

interface Change {
  id: string
  title: string
  parts: Part[]
}

const length = (days: number) => (days % 7 === 0 ? `${days / 7} tyg.` : `${days} dni`)

/** What differs between the example plan before and after the draft, per element. */
function changes(before: Timeline, after: Timeline): Change[] {
  const out: Change[] = []
  for (const s of after.segments) {
    const old = before.segments.find((b) => b.id === s.id)
    if (!old) continue
    const parts: Part[] = []
    if (old.days !== s.days) parts.push({ label: '', before: length(old.days), after: length(s.days) })
    if (old.start !== s.start) {
      parts.push({ label: 'od', before: formatShortDate(old.start), after: formatShortDate(s.start) })
    }
    if (old.end !== s.end) {
      parts.push({ label: 'do', before: formatShortDate(old.end), after: formatShortDate(s.end) })
    }
    if (parts.length) out.push({ id: s.id, title: s.title, parts })
  }
  for (const m of after.markers) {
    const old = before.markers.find((b) => b.id === m.id)
    if (old && old.date !== m.date) {
      out.push({
        id: m.id,
        title: m.title,
        parts: [{ label: '', before: formatShortDate(old.date), after: formatShortDate(m.date) }],
      })
    }
  }
  for (const d of after.documents) {
    const old = before.documents.find((b) => b.id === d.id)
    if (old && old.needed_by !== d.needed_by) {
      out.push({
        id: d.id,
        title: d.title,
        parts: [{ label: 'do', before: formatShortDate(old.needed_by), after: formatShortDate(d.needed_by) }],
      })
    }
  }
  for (const p of after.payments) {
    const old = before.payments.find((b) => b.id === p.id)
    if (!old) continue
    const parts: Part[] = []
    if (old.rate !== p.rate) parts.push({ label: '', before: formatRate(old.rate), after: formatRate(p.rate) })
    if (old.monthly !== p.monthly) {
      parts.push({ label: 'miesięcznie', before: formatPln(old.monthly), after: formatPln(p.monthly) })
    }
    if (parts.length) out.push({ id: p.id, title: p.title, parts })
  }
  return out
}

function PreviewDiff({ preview, dirty }: { preview: ParamPreview | null; dirty: boolean }) {
  const list = useMemo(() => (preview ? changes(preview.before, preview.after) : []), [preview])
  const span = (t: Timeline) => {
    const leave = t.segments.filter((s) => s.tone !== 'work')
    if (!leave.length) return [0, 0] as const
    return [
      Math.min(...leave.map((s) => dayNumber(s.start))),
      Math.max(...leave.map((s) => dayNumber(s.end) + 1)),
    ] as const
  }
  if (!preview) return <div className="mt-2 h-24 animate-pulse rounded-2xl bg-navy-50" />
  const [b0, b1] = span(preview.before)
  const [a0, a1] = span(preview.after)
  const from = Math.min(b0, a0)
  const to = Math.max(b1, a1, from + 1)
  const bar = (start: number, end: number) => ({
    left: `${((start - from) / (to - from)) * 100}%`,
    width: `${((end - start) / (to - from)) * 100}%`,
  })
  return (
    <div className="mt-2 rounded-2xl bg-navy-50/60 p-4">
      <div className="space-y-1.5">
        {(
          [
            ['Teraz', b0, b1, 'bg-navy-200'],
            ['Po zmianie', a0, a1, dirty ? 'bg-sun-400' : 'bg-navy-200'],
          ] as const
        ).map(([label, start, end, color]) => (
          <div key={label} className="flex items-center gap-2">
            <span className="w-20 text-xs font-bold text-navy-500">{label}</span>
            <div className="relative h-3 flex-1 rounded-full bg-white">
              <motion.span
                className={cn('absolute inset-y-0 rounded-full', color)}
                animate={bar(start, end)}
                transition={{ type: 'spring', stiffness: 300, damping: 32 }}
              />
            </div>
          </div>
        ))}
      </div>
      {dirty && list.length > 0 ? (
        <ul className="mt-3 space-y-2.5 text-sm">
          {list.map((c) => (
            <li key={c.id}>
              <p className="text-navy-700">{c.title}</p>
              <p className="flex flex-wrap gap-x-3">
                {c.parts.map((part) => (
                  <span key={part.label} className="whitespace-nowrap">
                    {part.label && <span className="text-navy-500">{part.label} </span>}
                    <span className="text-navy-400 line-through">{part.before}</span>{' '}
                    <span className="font-bold text-sun-700">{part.after}</span>
                  </span>
                ))}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-navy-500">
          {dirty ? 'Dla tej rodziny nic się nie zmienia.' : 'Zmień liczbę po lewej, żeby zobaczyć skutek.'}
        </p>
      )}
    </div>
  )
}

function History({ view }: { view: AdminView }) {
  const base = view.base.maternity
  const describe = (values: ParamValues) => {
    const out: string[] = []
    values.weeks_by_children.forEach((w, i) => {
      if (w !== base.weeks_by_children.value[i]) out.push(`${CHILDREN[i]}: ${base.weeks_by_children.value[i]} → ${w} tyg.`)
    })
    if (values.max_weeks_before_birth !== base.max_weeks_before_birth.value) {
      out.push(`Przed porodem: ${base.max_weeks_before_birth.value} → ${values.max_weeks_before_birth} tyg.`)
    }
    if (values.mother_personal_weeks !== base.mother_personal_weeks.value) {
      out.push(`Tylko dla mamy: ${base.mother_personal_weeks.value} → ${values.mother_personal_weeks} tyg.`)
    }
    for (const field of RATES) {
      const was = field.param(view.base).value
      if (values[field.key] !== was) out.push(`${field.label}: ${decimal(was)} → ${decimal(values[field.key])}%`)
    }
    for (const field of DEADLINES) {
      const was = field.param(view.base).value
      if (values[field.key] !== was) out.push(`${field.label}: ${was} → ${values[field.key]} dni`)
    }
    return out
  }
  const baseInForce = !view.versions.some((v) => v.status === 'in_force')
  return (
    <motion.section variants={ITEM} className="mt-5 rounded-3xl border border-line p-5">
      <h2 className="text-lg font-bold text-navy-900">Historia wersji</h2>
      <ol className="mt-3 space-y-3">
        <AnimatePresence initial={false}>
          {view.versions.map((v) => (
            <motion.li
              key={v.id}
              layout
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, ease: EASE_OUT }}
              className="rounded-2xl border border-line px-4 py-3"
            >
              <div className="flex items-center gap-2">
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-bold', STATUS[v.status].className)}>
                  {STATUS[v.status].label}
                </span>
                <span className="text-sm font-bold text-navy-900">od {formatShortDate(v.effective_from)}</span>
                <span className="ml-auto text-xs text-navy-400">{v.version}</span>
              </div>
              <p className="mt-1.5 text-sm text-navy-700">{v.note}</p>
              <ul className="mt-1 space-y-0.5 text-xs font-bold text-navy-500">
                {describe(v.values).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </motion.li>
          ))}
        </AnimatePresence>
        <li className="rounded-2xl border border-dashed border-line px-4 py-3">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-[11px] font-bold',
                baseInForce ? STATUS.in_force.className : STATUS.past.className,
              )}
            >
              {baseInForce ? 'Obowiązuje' : 'Bazowa'}
            </span>
            <span className="text-sm font-bold text-navy-900">Plik {view.base.version}</span>
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-navy-500">{view.base.description}</p>
        </li>
      </ol>
    </motion.section>
  )
}

function Loading() {
  return (
    <div className="mx-auto grid max-w-[1280px] gap-8 px-4 py-8 lg:grid-cols-[minmax(0,1fr)_400px] lg:px-8">
      <div className="space-y-5">
        <div className="h-10 w-72 animate-pulse rounded-2xl bg-navy-50" />
        <div className="h-48 animate-pulse rounded-3xl bg-navy-50" />
        <div className="h-36 animate-pulse rounded-3xl bg-navy-50" />
      </div>
      <div className="h-96 animate-pulse rounded-3xl bg-navy-50" />
    </div>
  )
}
