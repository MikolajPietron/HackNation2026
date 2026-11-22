// A request from the plan, as a form to fill in (FUNKCJE F22, ZADANIA B.3). The fields, the
// attachments and the notes are the engine's (`Document.form`): only what the regulations on
// leave requests (11.03.2025) and on benefit documents (27.09.2026) name. The app fills in what
// the timeline knows; personal data (names, PESEL, addresses) the parent types in, and it stays
// in this browser: the check sends only that such a field is filled in, never its content.
// "Sprawdź wniosek" (F23) checks the request with rules, without AI; AI only rewords the findings
// on request, and says so. Sending is a simulation, confirmed explicitly first (FUNKCJE: no undo
// for sending, a clear confirmation).
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  Check,
  ChevronDown,
  CircleAlert,
  Info,
  LoaderCircle,
  Lock,
  Printer,
  Send,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import { checkRequest } from '@/api'
import { SimBadge } from '@/components/mocks/MockModal'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import { Emphasis } from '@/components/ui/emphasis'
import { formatLongDate, formatShortDate, todayIso } from '@/lib/dates'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { currentSessionId } from '@/lib/session'
import { sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type {
  Document,
  FilledRequest,
  FormField,
  RequestCheckResult,
  RequestForm,
  RequestProblem,
  RequestSeverity,
  SourceRef,
  Timeline,
} from '@/types'

/** 2027-01-27 -> 27.01.2027, the way the forms write dates. */
const dotted = (iso: string | null) => (iso ? iso.split('-').reverse().join('.') : '')

/** What a personal field sends to the check: that it is filled in, not what it says. */
const FILLED = '(wpisane)'

type Step = 'fill' | 'send' | 'sent'
type Values = Record<string, string>

function initialValues(form: RequestForm): Values {
  const values: Values = {}
  for (const field of form.fields) {
    if (field.kind === 'period') {
      values[`${field.id}:from`] = dotted(field.start)
      values[`${field.id}:to`] = dotted(field.end)
    } else if (field.kind === 'date') {
      values[field.id] = dotted(field.start) || (field.value ?? '')
    } else {
      values[field.id] = field.personal ? '' : (field.value ?? '')
    }
  }
  return values
}

/** The field as the request says it (period: "od … do …"). */
function written(field: FormField, values: Values): string {
  if (field.kind === 'period') {
    const from = values[`${field.id}:from`]?.trim()
    const to = values[`${field.id}:to`]?.trim()
    return from || to ? `od ${from || '…'} do ${to || '…'}` : ''
  }
  return values[field.id]?.trim() ?? ''
}

/** Where the request goes, in the words of the button. */
const SEND_TO: Record<RequestForm['addressee'], { button: string; channel: 'email' | 'pue' }> = {
  employer: { button: 'Wyślij do pracodawcy', channel: 'email' },
  payer: { button: 'Wyślij do zleceniodawcy', channel: 'email' },
  zus: { button: 'Wyślij przez PUE/eZUS', channel: 'pue' },
  'payer-or-zus': { button: 'Wyślij do płatnika albo ZUS', channel: 'email' },
}

export function ApplicationForm({
  timeline,
  document,
  onSelect,
}: {
  timeline: Timeline
  document: Document
  /** Show the element a finding is about on the timeline. */
  onSelect?: (id: string) => void
}) {
  const form = document.form
  const [values, setValues] = useState<Values>(() => (form ? initialValues(form) : {}))
  const [attached, setAttached] = useState<Set<string>>(new Set())
  const [step, setStep] = useState<Step>('fill')
  const [email, setEmail] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [check, setCheck] = useState<CheckState>({ status: 'idle' })

  if (!form) return null
  const set = (key: string) => (value: string) => {
    setValues((v) => ({ ...v, [key]: value }))
    if (check.status === 'done') setCheck({ status: 'stale', result: check.result })
  }
  const toggle = (id: string) => {
    setAttached((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
    if (check.status === 'done') setCheck({ status: 'stale', result: check.result })
  }

  const filled = (): FilledRequest => ({
    title: form.title,
    addressee: form.addressee_label,
    form_id: document.id,
    parent: form.applicant,
    fields: form.fields.map((field) => {
      const value = written(field, values)
      return {
        label: field.label,
        id: field.id,
        required: field.required,
        value: field.personal ? (value ? FILLED : null) : value || null,
      }
    }),
    attachments: form.attachments.filter((a) => attached.has(a.id)).map((a) => a.label),
  })

  const runCheck = async (phrase = false) => {
    setCheck((c) => ({ status: 'checking', result: c.result, phrasing: phrase }))
    try {
      const result = await checkRequest({ request: filled(), session_id: currentSessionId(), phrase })
      setCheck({ status: 'done', result })
    } catch (error) {
      setCheck({ status: 'error', error: error instanceof Error ? error.message : 'Nie udało się sprawdzić wniosku.' })
    }
  }

  const print = () => printRequest(form, document, values, attached)
  const send = SEND_TO[form.addressee]
  const deadlinePassed = document.deadline !== null && document.deadline < timeline.today

  return (
    <div className="text-navy-700">
      <header className="pr-10">
        <SimBadge>symulacja · nic nie jest wysyłane</SimBadge>
        <h2 className="mt-3 text-2xl leading-tight font-bold tracking-tight text-navy-900">{form.title}</h2>
        <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
          <span className="rounded-full bg-navy-50 px-2.5 py-1 text-navy-700">Do: {form.addressee_label}</span>
          {form.official_form && (
            <span className="rounded-full bg-navy-50 px-2.5 py-1 text-navy-700">formularz {form.official_form}</span>
          )}
          {document.deadline ? (
            <span
              className={cn(
                'rounded-full px-2.5 py-1',
                deadlinePassed ? 'bg-alert-50 text-alert-600' : 'bg-sun-100 text-sun-700',
              )}
            >
              {deadlinePassed
                ? `termin minął ${formatShortDate(document.deadline)}`
                : `złóż najpóźniej ${formatShortDate(document.deadline)}`}
            </span>
          ) : (
            <span className="rounded-full bg-navy-50 px-2.5 py-1 text-navy-500">
              na dzień startu: {formatShortDate(document.needed_by)}
            </span>
          )}
        </div>
      </header>

      <AnimatePresence mode="wait" initial={false}>
        {step === 'fill' && (
          <motion.div key="fill" {...fade}>
            {form.notes.length > 0 && (
              <ul className="mt-5 space-y-1.5 text-sm text-navy-500">
                {form.notes.map((note) => (
                  <li key={note.text} className="flex gap-2">
                    <Info className="mt-0.5 size-4 shrink-0 text-navy-400" />
                    <Emphasis text={note.text} className="text-navy-700" />
                  </li>
                ))}
              </ul>
            )}

            <section aria-label="Pola wniosku" className="mt-5 space-y-4">
              {form.fields.map((field) => (
                <FieldRow key={field.id} field={field} values={values} set={set} />
              ))}
            </section>

            {form.attachments.length > 0 && (
              <section className="mt-6">
                <h3 className="font-bold text-navy-900">Załączniki</h3>
                <p className="mt-0.5 text-sm text-navy-500">Zaznacz to, co już masz.</p>
                <ul className="mt-3 space-y-2">
                  {form.attachments.map((attachment) => {
                    const on = attached.has(attachment.id)
                    return (
                      <li key={attachment.id}>
                        <label
                          className={cn(
                            'flex cursor-pointer items-start gap-3 rounded-2xl border px-4 py-3 transition-[border-color,background-color] duration-150',
                            on ? 'border-zus-600 bg-zus-50/60' : 'border-line hover:border-navy-200',
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={on}
                            onChange={() => toggle(attachment.id)}
                            className="mt-1 size-4 shrink-0 accent-[var(--color-zus-600)]"
                          />
                          <span className="min-w-0 text-sm">
                            <span className="font-bold text-navy-900">{attachment.label}</span>
                            {!attachment.required && <span className="text-navy-400"> · jeśli dotyczy</span>}
                            {attachment.hint && <span className="mt-0.5 block text-navy-500">{attachment.hint}</span>}
                          </span>
                        </label>
                      </li>
                    )
                  })}
                </ul>
              </section>
            )}

            <LegalBasis sources={form.legal_basis} />

            <CheckPanel check={check} onPhrase={() => void runCheck(true)} onSelect={onSelect} />

            <p className="mt-4 flex items-start gap-2 text-xs text-navy-400">
              <Lock className="mt-px size-3.5 shrink-0" />
              Imię, nazwisko i inne dane osobowe zostają tylko w tej przeglądarce: nie zapisujemy ich i nigdzie
              nie wysyłamy, także przy sprawdzaniu wniosku.
            </p>

            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
              <Secondary onClick={print}>
                <Printer className="size-4" /> Drukuj albo PDF
              </Secondary>
              <Secondary onClick={() => void runCheck()} disabled={check.status === 'checking'}>
                {check.status === 'checking' && !check.phrasing ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <ShieldCheck className="size-4" />
                )}
                {check.status === 'stale' ? 'Sprawdź ponownie' : 'Sprawdź wniosek'}
              </Secondary>
              <PrimaryButton onClick={() => setStep('send')} className="h-12 px-6 text-base">
                <Send className="size-4" /> {send.button}
              </PrimaryButton>
            </div>
          </motion.div>
        )}

        {step === 'send' && (
          <motion.div key="send" {...fade} className="mt-5">
            {send.channel === 'email' ? (
              <>
                <label className="block font-bold text-navy-900" htmlFor="send-email">
                  Adres e-mail: {form.addressee_label.toLowerCase()}
                </label>
                <input
                  id="send-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="kadry@firma.pl"
                  className="mt-2 h-11 w-full rounded-2xl border border-line px-4 text-navy-900 outline-none focus:border-zus-400 focus:ring-4 focus:ring-zus-600/10"
                />
              </>
            ) : (
              <p className="rounded-2xl bg-navy-50/60 px-4 py-3 text-sm">
                Wniosek trafi do ZUS przez Platformę Usług Elektronicznych (PUE/eZUS).
              </p>
            )}
            <div className="mt-3 rounded-2xl bg-navy-50/60 px-4 py-3 text-sm">
              <p className="font-bold text-navy-900">{form.title}</p>
              <ul className="mt-1 space-y-0.5 text-navy-500">
                {form.fields
                  .filter((f) => !f.personal && written(f, values))
                  .map((f) => (
                    <li key={f.id} className="line-clamp-1">
                      {f.label}: <span className="text-navy-900">{written(f, values)}</span>
                    </li>
                  ))}
              </ul>
            </div>
            <AnimatePresence initial={false}>
              {confirming && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, transition: { duration: 0.12 } }}
                  transition={{ duration: 0.2, ease: EASE_OUT }}
                  className="mt-4 rounded-2xl border border-sun-300 bg-sun-100 px-4 py-3 text-sm text-sun-700"
                  role="alertdialog"
                  aria-label="Potwierdź wysłanie"
                >
                  <p className="font-bold text-navy-900">
                    Wysłać wniosek {send.channel === 'pue' ? 'do ZUS' : `na adres ${email}`}?
                  </p>
                  <p className="mt-0.5">To symulacja: nic nie wyjdzie z aplikacji.</p>
                  <div className="mt-3 flex gap-2">
                    <PrimaryButton onClick={() => setStep('sent')} className="h-10 px-4 text-sm">
                      Tak, wyślij
                    </PrimaryButton>
                    <Secondary onClick={() => setConfirming(false)}>Anuluj</Secondary>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            {!confirming && (
              <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Secondary onClick={() => setStep('fill')}>Wróć do wniosku</Secondary>
                <PrimaryButton
                  onClick={() => setConfirming(true)}
                  disabled={send.channel === 'email' && !email.includes('@')}
                  className="h-12 px-6 text-base"
                >
                  <Send className="size-4" /> Wyślij
                </PrimaryButton>
              </div>
            )}
          </motion.div>
        )}

        {step === 'sent' && (
          <motion.div key="sent" {...fade} className="mt-8 flex flex-col items-center pb-2 text-center">
            <motion.span
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 380, damping: 22 }}
              className="grid size-16 place-items-center rounded-full bg-zus-600 text-white"
            >
              <Check className="size-8" strokeWidth={3} />
            </motion.span>
            <p className="mt-4 text-xl font-bold text-navy-900">Wniosek wysłany</p>
            <p className="mt-1 text-sm text-navy-500">
              {send.channel === 'pue' ? 'Do ZUS' : `Na ${email}`} · {formatLongDate(todayIso())} · symulacja, nic nie
              zostało wysłane
            </p>
            <p className="mt-4 max-w-sm text-sm text-pretty">Zachowaj kopię wniosku.</p>
            <div className="mt-5">
              <Secondary onClick={print}>
                <Printer className="size-4" /> Zachowaj kopię (PDF)
              </Secondary>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

const fade = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6, transition: { duration: 0.12 } },
  transition: { duration: 0.22, ease: EASE_OUT },
}

// ---------------------------------------------------------------------------------------------
// Fields

const input =
  'h-11 w-full rounded-2xl border border-line bg-white px-4 text-navy-900 outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-navy-300 focus:border-zus-400 focus:ring-4 focus:ring-zus-600/10'

function FieldRow({ field, values, set }: { field: FormField; values: Values; set: (key: string) => (value: string) => void }) {
  const id = `field-${field.id}`
  const fromPlan = !field.personal && field.value !== null
  return (
    <div>
      <label htmlFor={field.kind === 'period' ? `${id}-from` : id} className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-sm font-bold text-navy-900">{field.label}</span>
        {!field.required && <span className="text-xs text-navy-400">jeśli dotyczy</span>}
        {fromPlan && (
          <span className="rounded-full bg-zus-50 px-2 py-0.5 text-[11px] font-bold text-zus-700">z planu</span>
        )}
        {field.personal && (
          <span className="flex items-center gap-1 rounded-full bg-navy-50 px-2 py-0.5 text-[11px] font-bold text-navy-500">
            <Lock className="size-3" /> dane osobowe
          </span>
        )}
      </label>
      <div className="mt-1.5">
        {field.kind === 'period' ? (
          <div className="grid grid-cols-2 gap-2">
            <DateInput id={`${id}-from`} label="od" value={values[`${field.id}:from`] ?? ''} onChange={set(`${field.id}:from`)} />
            <DateInput id={`${id}-to`} label="do" value={values[`${field.id}:to`] ?? ''} onChange={set(`${field.id}:to`)} />
          </div>
        ) : field.kind === 'date' ? (
          <DateInput id={id} value={values[field.id] ?? ''} onChange={set(field.id)} />
        ) : field.kind === 'statement' ? (
          <textarea
            id={id}
            value={values[field.id] ?? ''}
            onChange={(e) => set(field.id)(e.target.value)}
            rows={2}
            className={cn(input, 'h-auto min-h-11 resize-y py-2.5 leading-relaxed')}
          />
        ) : (
          <input
            id={id}
            value={values[field.id] ?? ''}
            onChange={(e) => set(field.id)(e.target.value)}
            autoComplete={field.personal ? 'off' : undefined}
            className={input}
          />
        )}
      </div>
      {field.kind === 'period' && field.value && <p className="mt-1 text-xs text-navy-400">Na osi: {field.value}</p>}
      {field.hint && <p className="mt-1 text-xs text-navy-400">{field.hint}</p>}
    </div>
  )
}

/** A date written the way forms write it (DD.MM.RRRR), with a label inside when there is one. */
function DateInput({
  id,
  label,
  value,
  onChange,
}: {
  id: string
  label?: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <span className="relative block">
      {label && (
        <span className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-sm text-navy-400">{label}</span>
      )}
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        inputMode="numeric"
        placeholder="DD.MM.RRRR"
        aria-label={label}
        className={cn(input, 'tabular-nums', label && 'pl-11')}
      />
    </span>
  )
}

function LegalBasis({ sources }: { sources: SourceRef[] }) {
  const [open, setOpen] = useState(false)
  if (sources.length === 0) return null
  return (
    <div className="mt-6">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-sm font-bold text-zus-700"
      >
        Podstawa prawna
        <ChevronDown className={cn('size-4 transition-transform duration-200', open && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
            transition={{ duration: 0.22, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <div className="space-y-3 pt-3 text-sm">
              {sources.map((source) => (
                <figure key={source.quote}>
                  <blockquote className="text-navy-700">„{source.quote}”</blockquote>
                  <figcaption className="mt-1 text-navy-400">{sourceLabel(source)}</figcaption>
                </figure>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// The check (F23)

type CheckState =
  | { status: 'idle'; result?: undefined; phrasing?: undefined }
  | { status: 'checking'; result?: RequestCheckResult; phrasing: boolean }
  | { status: 'done'; result: RequestCheckResult; phrasing?: undefined }
  | { status: 'stale'; result: RequestCheckResult; phrasing?: undefined }
  | { status: 'error'; error: string; result?: undefined; phrasing?: undefined }

const SEVERITY: Record<RequestSeverity, { icon: typeof Info; tone: string; label: string }> = {
  error: { icon: CircleAlert, tone: 'text-alert-600', label: 'Do poprawy' },
  warning: { icon: TriangleAlert, tone: 'text-sun-700', label: 'Sprawdź' },
  info: { icon: Info, tone: 'text-navy-500', label: 'Dla informacji' },
}
const ORDER: RequestSeverity[] = ['error', 'warning', 'info']

function CheckPanel({
  check,
  onPhrase,
  onSelect,
}: {
  check: CheckState
  onPhrase: () => void
  onSelect?: (id: string) => void
}) {
  const result = check.result
  const ref = useRef<HTMLElement>(null)
  const reduce = useReducedMotion()
  // A fresh result comes into view: it is usually below the fields.
  useEffect(() => {
    if (check.status !== 'done') return
    const timer = window.setTimeout(
      () => ref.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'nearest' }),
      60,
    )
    return () => window.clearTimeout(timer)
  }, [check.status, result, reduce])
  return (
    <AnimatePresence initial={false}>
      {check.status === 'error' && (
        <motion.p key="error" {...fade} role="alert" className="mt-6 rounded-2xl bg-alert-50 px-4 py-3 text-sm font-bold text-alert-600">
          {check.error}
        </motion.p>
      )}
      {result && (
        <motion.section
          ref={ref}
          key="result"
          {...fade}
          aria-live="polite"
          className={cn('mt-6 rounded-3xl border border-line p-4 transition-opacity', check.status === 'stale' && 'opacity-60')}
        >
          <header className="flex items-start gap-3">
            <span
              className={cn(
                'grid size-9 shrink-0 place-items-center rounded-full',
                result.ok ? 'bg-zus-600 text-white' : 'bg-alert-50 text-alert-600',
              )}
            >
              {result.ok ? <Check className="size-5" strokeWidth={3} /> : <CircleAlert className="size-5" />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-bold text-navy-900">
                {result.ok
                  ? result.problems.length === 0
                    ? 'Wniosek wygląda dobrze'
                    : 'Bez błędów, ale sprawdź uwagi'
                  : `Do poprawy: ${result.problems.filter((p) => p.severity === 'error').length}`}
              </p>
              <p className="text-sm text-navy-500">
                {check.status === 'stale'
                  ? 'Wniosek się zmienił: sprawdź go ponownie.'
                  : `Sprawdziliśmy regułami z przepisów (${result.checks.length}), bez AI${result.timeline_used ? ', z Waszą osią czasu' : ''}.`}
              </p>
            </div>
          </header>
          {result.problems.length > 0 && (
            <ul className="mt-4 space-y-3">
              {[...result.problems]
                .sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity))
                .map((problem) => (
                  <Problem key={problem.id} problem={problem} onSelect={onSelect} />
                ))}
            </ul>
          )}
          {result.problems.length > 0 && !result.ai && (
            <button
              type="button"
              onClick={onPhrase}
              disabled={check.status === 'checking'}
              className="mt-4 flex h-9 items-center gap-2 rounded-full border border-line px-3.5 text-sm font-bold text-navy-700 transition-colors hover:bg-navy-50 disabled:opacity-50"
            >
              {check.status === 'checking' && check.phrasing ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4 text-zus-600" />
              )}
              Wyjaśnij prościej
              <span className="rounded-full bg-zus-50 px-1.5 py-0.5 text-[10px] font-black text-zus-700">AI</span>
            </button>
          )}
          {result.ai && result.ai_note && <p className="mt-3 text-xs text-navy-400">{result.ai_note}</p>}
        </motion.section>
      )}
    </AnimatePresence>
  )
}

function Problem({ problem, onSelect }: { problem: RequestProblem; onSelect?: (id: string) => void }) {
  const look = SEVERITY[problem.severity]
  const Icon = look.icon
  return (
    <li className="flex gap-3">
      <Icon className={cn('mt-0.5 size-4 shrink-0', look.tone)} />
      <div className="min-w-0 flex-1 text-sm">
        <p className={cn('text-xs font-bold', look.tone)}>
          {look.label}
          {problem.field && <span className="font-normal text-navy-400"> · {problem.field}</span>}
        </p>
        {problem.phrased ? (
          <>
            <p className="mt-0.5 text-navy-900">
              {problem.phrased}{' '}
              <span className="rounded-full bg-zus-50 px-1.5 py-0.5 align-middle text-[10px] font-black text-zus-700">AI</span>
            </p>
            <p className="mt-1 text-xs text-navy-400">Reguła: {problem.message}</p>
          </>
        ) : (
          <p className="mt-0.5 text-navy-900">{problem.message}</p>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {problem.sources.slice(0, 2).map((source) => (
            <span key={source.quote} className="text-navy-400" title={source.quote}>
              {sourceLabel(source)}
            </span>
          ))}
          {problem.element_id && onSelect && (
            <button
              type="button"
              onClick={() => onSelect(problem.element_id!)}
              className="font-bold text-zus-700 hover:text-zus-900"
            >
              Pokaż na osi
            </button>
          )}
        </div>
      </div>
    </li>
  )
}

// ---------------------------------------------------------------------------------------------

function Secondary({ onClick, disabled, children }: { onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={disabled}
      whileTap={disabled ? undefined : { scale: 0.97, transition: SPRING_PRESS }}
      className="flex h-12 items-center justify-center gap-2 rounded-full border border-line px-5 font-bold text-navy-700 transition-[border-color,background-color,opacity] duration-150 hover:border-navy-200 hover:bg-navy-50 disabled:opacity-60"
    >
      {children}
    </motion.button>
  )
}

/** The request on paper: what the parent typed stays in this window only. */
function printRequest(form: RequestForm, document: Document, values: Values, attached: Set<string>) {
  const win = window.open('', '_blank', 'noopener=no')
  if (!win) return
  const esc = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;')
  const rows = form.fields
    .map((f) => `<tr><th>${esc(f.label)}</th><td>${esc(written(f, values) || '……………………………')}</td></tr>`)
    .join('')
  const attachments = form.attachments
    .map((a) => `<li>${attached.has(a.id) ? '☒' : '☐'} ${esc(a.label)}</li>`)
    .join('')
  const basis = form.legal_basis.map((s) => esc(sourceLabel(s))).join('; ')
  win.document.write(`<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>${esc(form.title)}</title>
<style>body{font-family:Georgia,serif;max-width:680px;margin:48px auto;line-height:1.55;color:#111}
.r{text-align:right}h1{font-size:20px;text-align:center;margin:36px 0 24px}table{width:100%;border-collapse:collapse}
th,td{text-align:left;vertical-align:top;padding:8px 0;border-bottom:1px solid #ddd}th{width:45%;font-weight:normal;color:#555;padding-right:16px}
ul{list-style:none;padding:0}.s{margin-top:64px;text-align:right}.b{margin-top:24px;font-size:12px;color:#555}</style></head><body>
<p class="r">……………, ${esc(formatLongDate(todayIso()))} r.</p>
<p class="r">${esc(form.addressee_label)}</p>
<h1>${esc(form.title)}</h1><table>${rows}</table>
${attachments ? `<p><b>Załączniki</b></p><ul>${attachments}</ul>` : ''}
<p class="s">……………………………<br>podpis</p>
${basis ? `<p class="b">Podstawa: ${basis}</p>` : ''}
<p class="b">${esc(document.title)} · przygotowane w aplikacji Zasiłkowy Przewodnik Przyszłego Rodzica (symulacja).</p>
</body></html>`)
  win.document.close()
  win.focus()
  win.print()
}
