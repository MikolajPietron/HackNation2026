// A request from the plan, filled in on the document itself (RequestPaper: a ZUS form or the
// letter to the employer; FUNKCJE F22, ZADANIA B.3). The fields, the
// attachments and the notes are the engine's (`Document.form`): only what the regulations on
// leave requests (11.03.2025) and on benefit documents (27.09.2026) name. The app fills in what
// the timeline knows; personal data (names, PESEL, addresses) the parent types in, and it stays
// in this browser: the check sends only that such a field is filled in, never its content.
// "Sprawdź wniosek" (F23) checks the request with rules, without AI; AI only rewords the findings
// on request, and says so. What it finds about a field shows under that field on the paper, next
// to the format checks of this browser (PESEL, account, NIP, dates: lib/validate.ts); near the
// button stays one line of summary and what belongs to no field. Sending is a simulation,
// confirmed explicitly first (FUNKCJE: no undo for sending, a clear confirmation).
import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode, Ref } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  Check,
  ChevronDown,
  CircleAlert,
  Info,
  LoaderCircle,
  Download,
  Lock,
  Mail,
  Send,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { checkRequest } from '@/api'
import { RequestPaper, type PaperCheck } from '@/components/applications/RequestPaper'
import { SimBadge } from '@/components/mocks/MockModal'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import { Emphasis } from '@/components/ui/emphasis'
import { FieldError, type FieldIssue, type FieldTone } from '@/components/ui/field-error'
import { useFieldErrors } from '@/hooks/useFieldErrors'
import { formatLongDate, formatShortDate, todayIso } from '@/lib/dates'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { personalValue, useProfile, withPersonalValue, type Profile } from '@/lib/personal'
import { currentSessionId } from '@/lib/session'
import { copyText } from '@/lib/clipboard'
import { sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import { accountError, dateError, nipError, peselError } from '@/lib/validate'
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

function initialValues(form: RequestForm, profile: Profile): Values {
  const values: Values = {}
  for (const field of form.fields) {
    if (field.kind === 'period') {
      values[`${field.id}:from`] = dotted(field.start)
      values[`${field.id}:to`] = dotted(field.end)
    } else if (field.kind === 'date') {
      values[field.id] = dotted(field.start) || (field.value ?? '')
    } else {
      values[field.id] = field.personal ? personalValue(field, form, profile) : (field.value ?? '')
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

/** The keys of a field's values: a period has two dates. */
const valueKeys = (field: FormField) => (field.kind === 'period' ? [`${field.id}:from`, `${field.id}:to`] : [field.id])

/**
 * The format check of one value on the paper, in this browser: dates as the server reads them,
 * PESEL, the bank account and NIP. A date the plan wrote in words is the plan's, not checked.
 */
function formatError(field: FormField, value: string): string | null {
  if (field.kind === 'date' || field.kind === 'period') return value === field.value ? null : dateError(value)
  if (!field.personal) return null
  if (/pesel/.test(field.id)) return peselError(value, { passport: /paszport/i.test(field.label) })
  if (field.id === 'bank-account') return accountError(value)
  if (/nip/.test(field.id)) return nipError(value, { withRegon: /regon/i.test(field.label) })
  return null
}

/** Which date of a period a message is about. */
const part = (key: string) => (key.endsWith(':from') ? 'Data „od”: ' : key.endsWith(':to') ? 'Data „do”: ' : '')

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
  onCertificate,
}: {
  timeline: Timeline
  document: Document
  /** Show the element a finding is about on the timeline. */
  onSelect?: (id: string) => void
  /** Order the birth certificate (a simulation, F35). */
  onCertificate?: () => void
}) {
  const form = document.form
  const [profile, saveProfile] = useProfile()
  const [values, setValues] = useState<Values>(() => (form ? initialValues(form, profile) : {}))
  const [downloading, setDownloading] = useState(false)
  const [hrOpen, setHrOpen] = useState(false)
  const [attached, setAttached] = useState<Set<string>>(new Set())
  const [step, setStep] = useState<Step>('fill')
  const [email, setEmail] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [check, setCheck] = useState<CheckState>({ status: 'idle' })
  /** Fields typed in since the last check: what the check said about them may no longer hold. */
  const [edited, setEdited] = useState<ReadonlySet<string>>(() => new Set())
  const errors = useFieldErrors()
  const paperRef = useRef<HTMLDivElement>(null)
  const summaryRef = useRef<HTMLDivElement>(null)
  const ids = useId()
  const reduce = useReducedMotion()

  // A fresh result: bring the first field it marks into view (the button is below the paper);
  // when nothing is marked on a field, the summary next to the button.
  useEffect(() => {
    if (check.status !== 'done') return
    const timer = window.setTimeout(() => {
      const paper = paperRef.current
      const target =
        paper?.querySelector<HTMLElement>('[data-issue="error"]') ??
        paper?.querySelector<HTMLElement>('[data-issue="warning"]') ??
        summaryRef.current
      target?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: target === summaryRef.current ? 'nearest' : 'center' })
    }, 80)
    return () => window.clearTimeout(timer)
  }, [check.status, check.result, reduce])

  if (!form) return null
  const fieldOf = (key: string) => form.fields.find((f) => f.id === key.split(':')[0])
  const localError = (key: string) => {
    const field = fieldOf(key)
    return field ? formatError(field, values[key] ?? '') : null
  }
  const allKeys = form.fields.flatMap(valueKeys)
  const failing = () => allKeys.filter((key) => localError(key))

  const set = (key: string) => (value: string) => {
    setValues((v) => ({ ...v, [key]: value }))
    // Personal data typed here fills every other request too (kept in this browser only).
    const field = fieldOf(key)
    if (field?.personal) saveProfile(withPersonalValue(profile, field, form, value))
    errors.change(key, field ? formatError(field, value) : null)
    if (field && check.result && !edited.has(field.id)) setEdited(new Set(edited).add(field.id))
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
    // The format errors of this browser show too: they are part of the check.
    errors.showAll(failing())
    setCheck((c) => ({ status: 'checking', result: c.result, phrasing: phrase }))
    try {
      const result = await checkRequest({ request: filled(), session_id: currentSessionId(), phrase })
      setEdited(new Set())
      setCheck({ status: 'done', result })
    } catch (error) {
      setCheck({ status: 'error', error: error instanceof Error ? error.message : 'Nie udało się sprawdzić wniosku.' })
    }
  }

  const download = async () => {
    setDownloading(true)
    try {
      const { downloadRequest } = await import('@/lib/pdf/documents')
      await downloadRequest(document, values, profile, attached)
    } finally {
      setDownloading(false)
    }
  }
  const send = SEND_TO[form.addressee]
  const deadlinePassed = document.deadline !== null && document.deadline < timeline.today

  // What the check found, placed under its field (by the field's label, which the check names);
  // the rest stays in the summary. A field typed in since the check drops its findings.
  const byField = new Map<string, RequestProblem[]>()
  const unplaced: RequestProblem[] = []
  for (const problem of check.result?.problems ?? []) {
    const field = problem.field ? form.fields.find((f) => f.label === problem.field) : undefined
    if (!field) unplaced.push(problem)
    else if (!edited.has(field.id)) byField.set(field.id, [...(byField.get(field.id) ?? []), problem])
  }
  const shownErrors = allKeys.filter((key) => errors.shown(key, localError(key)))
  const placed = [...byField.values()].flat()

  const paperCheck: PaperCheck = {
    id: (field) => `${ids}-${field.id}`,
    issues: (field) => [
      ...valueKeys(field).flatMap((key) => {
        const message = errors.shown(key, localError(key))
        return message ? [{ key, tone: 'error' as const, text: part(key) + message }] : []
      }),
      ...sortProblems(byField.get(field.id) ?? []).map((problem) => problemIssue(problem, onSelect, true)),
    ],
    tone: (key) => {
      if (errors.shown(key, localError(key))) return 'error'
      const problems = byField.get(key.split(':')[0]) ?? []
      if (problems.some((p) => p.severity === 'error')) return 'error'
      if (problems.some((p) => p.severity === 'warning')) return 'warning'
      return null
    },
    blur: (key) => errors.blur(key, localError(key)),
  }

  /** "Wyślij": a wrong PESEL, account, NIP or date has to be fixed first; it is marked at its field. */
  const toSend = () => {
    const wrong = failing()
    if (wrong.length === 0) return setStep('send')
    errors.showAll(wrong)
    const row = paperRef.current?.querySelector<HTMLElement>(`[data-field="${wrong[0].split(':')[0]}"]`)
    const input = row?.querySelectorAll<HTMLInputElement>('input, textarea')[wrong[0].endsWith(':to') ? 1 : 0]
    input?.focus({ preventScroll: true })
    row?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' })
  }

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

            <div ref={paperRef}>
              <RequestPaper
                form={form}
                values={values}
                set={set}
                profile={profile}
                saveProfile={saveProfile}
                attached={attached}
                toggle={toggle}
                today={timeline.today}
                onCertificate={onCertificate}
                check={paperCheck}
              />
            </div>

            <LegalBasis sources={form.legal_basis} />

            <p className="mt-4 flex items-start gap-2 text-xs text-navy-400">
              <Lock className="mt-px size-3.5 shrink-0" />
              Imię, nazwisko i inne dane osobowe zostają tylko w tej przeglądarce: nie zapisujemy ich i nigdzie
              nie wysyłamy, także przy sprawdzaniu wniosku.
            </p>

            <CheckSummary
              ref={summaryRef}
              id={`${ids}-summary`}
              check={check}
              localErrors={shownErrors.length}
              placed={placed}
              unplaced={unplaced}
              onPhrase={() => void runCheck(true)}
              onSelect={onSelect}
            />

            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
              {form.addressee === 'employer' && (
                <Secondary onClick={() => setHrOpen((o) => !o)}>
                  <Mail className="size-4" /> Wiadomość do kadr
                </Secondary>
              )}
              <Secondary onClick={() => void download()} disabled={downloading}>
                {downloading ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}
                {form.official_form ? `Dane do ${form.official_form} (PDF)` : 'Pobierz wniosek (PDF)'}
              </Secondary>
              <Secondary onClick={() => void runCheck()} disabled={check.status === 'checking'}>
                {check.status === 'checking' && !check.phrasing ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <ShieldCheck className="size-4" />
                )}
                {check.status === 'stale' ? 'Sprawdź ponownie' : 'Sprawdź wniosek'}
              </Secondary>
              <PrimaryButton onClick={toSend} className="h-12 px-6 text-base">
                <Send className="size-4" /> {send.button}
              </PrimaryButton>
            </div>
            <AnimatePresence initial={false}>
              {hrOpen && <HrMessage form={form} profile={profile} onClose={() => setHrOpen(false)} />}
            </AnimatePresence>
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
              <Secondary onClick={() => void download()} disabled={downloading}>
                {downloading ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}
                Zachowaj kopię (PDF)
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

const ORDER: RequestSeverity[] = ['error', 'warning', 'info']
const sortProblems = (problems: RequestProblem[]) =>
  [...problems].sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity))

function AiBadge() {
  return (
    <span className="rounded-full bg-zus-50 px-1.5 py-0.5 align-middle text-[10px] font-black text-zus-700">AI</span>
  )
}

/**
 * A finding of the check as a line under its field (or in the summary): the same look as a format
 * error. Under its own field an empty field does not repeat the label: "Uzupełnij to pole."
 */
function problemIssue(problem: RequestProblem, onSelect?: (id: string) => void, atField = false): FieldIssue {
  // Two quotes from the same page read the same: one label each.
  const sources = problem.sources.filter((source, i, all) => all.findIndex((s) => sourceLabel(s) === sourceLabel(source)) === i).slice(0, 2)
  const link = problem.element_id && onSelect ? problem.element_id : null
  const extra =
    problem.phrased || sources.length > 0 || link ? (
      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-xs text-navy-400">
        {problem.phrased && <span>Reguła: {problem.message}</span>}
        {sources.map((source) => (
          <span key={sourceLabel(source)} title={source.quote}>
            {sourceLabel(source)}
          </span>
        ))}
        {link && (
          <button type="button" onClick={() => onSelect!(link)} className="font-bold text-zus-700 hover:text-zus-900">
            Pokaż na osi
          </button>
        )}
      </p>
    ) : undefined
  return {
    key: problem.id,
    tone: problem.severity as FieldTone,
    text: problem.phrased ? (
      <>
        {problem.phrased} <AiBadge />
      </>
    ) : atField && problem.check === 'field-empty' ? (
      'Uzupełnij to pole.'
    ) : (
      problem.message
    ),
    extra,
  }
}

/**
 * One line next to "Sprawdź wniosek": how many things to fix and that they are marked at their
 * fields; below it only what belongs to no field, the AI rewording on request and its note.
 */
function CheckSummary({
  ref,
  id,
  check,
  localErrors,
  placed,
  unplaced,
  onPhrase,
  onSelect,
}: {
  ref: Ref<HTMLDivElement>
  id: string
  check: CheckState
  /** Format errors of this browser shown under the fields. */
  localErrors: number
  /** The check's findings shown under their fields. */
  placed: RequestProblem[]
  unplaced: RequestProblem[]
  onPhrase: () => void
  onSelect?: (id: string) => void
}) {
  const result = check.result
  const count = (problems: RequestProblem[], severity: RequestSeverity) =>
    problems.filter((p) => p.severity === severity).length
  const atFields = localErrors + count(placed, 'error')
  const fixes = atFields + count(unplaced, 'error')
  const notes = placed.length + unplaced.length - count(placed, 'error') - count(unplaced, 'error')
  const where = (here: number, below: number) =>
    here > 0 && below > 0 ? ' — przy polach i niżej' : here > 0 ? ' — zaznaczyliśmy je przy polach' : ''
  const title =
    fixes > 0
      ? `Do poprawy: ${fixes}${where(atFields, count(unplaced, 'error'))}`
      : notes > 0
        ? `Bez błędów, ale sprawdź uwagi${placed.length > 0 && unplaced.length === 0 ? ' przy polach' : ''}`
        : 'Wniosek wygląda dobrze'
  return (
    <div ref={ref} className="scroll-mt-4">
      <AnimatePresence initial={false}>
        {check.status === 'error' && (
          <motion.p key="error" {...fade} role="alert" className="mt-5 flex gap-2 text-sm font-bold text-alert-600">
            <CircleAlert className="mt-0.5 size-4 shrink-0" />
            {check.error}
          </motion.p>
        )}
        {result && (
          <motion.section
            key="result"
            {...fade}
            aria-live="polite"
            className={cn('mt-5 rounded-2xl border border-line px-4 py-3 transition-opacity', check.status === 'stale' && 'opacity-70')}
          >
            <header className="flex items-start gap-3">
              <span
                className={cn(
                  'mt-0.5 grid size-7 shrink-0 place-items-center rounded-full',
                  fixes === 0 ? 'bg-zus-600 text-white' : 'bg-alert-50 text-alert-600',
                )}
              >
                {fixes === 0 ? <Check className="size-4" strokeWidth={3} /> : <CircleAlert className="size-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-bold text-navy-900">{title}</p>
                <p className="text-sm text-navy-500">
                  {check.status === 'stale'
                    ? 'Wniosek się zmienił: sprawdź go ponownie.'
                    : `Sprawdziliśmy regułami z przepisów (${result.checks.length}), bez AI${result.timeline_used ? ', z Waszą osią czasu' : ''}.`}
                </p>
              </div>
            </header>
            {unplaced.length > 0 && (
              <FieldError id={id} issues={sortProblems(unplaced).map((p) => problemIssue(p, onSelect))} className="mt-1.5 pl-10" />
            )}
            {result.problems.length > 0 && !result.ai && (
              <button
                type="button"
                onClick={onPhrase}
                disabled={check.status === 'checking'}
                className="mt-3 ml-10 flex h-9 items-center gap-2 rounded-full border border-line px-3.5 text-sm font-bold text-navy-700 transition-colors hover:bg-navy-50 disabled:opacity-50"
              >
                {check.status === 'checking' && check.phrasing ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <Sparkles className="size-4 text-zus-600" />
                )}
                Wyjaśnij prościej
                <AiBadge />
              </button>
            )}
            {result.ai && result.ai_note && <p className="mt-2 pl-10 text-xs text-navy-400">{result.ai_note}</p>}
          </motion.section>
        )}
      </AnimatePresence>
    </div>
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

/** A short e-mail to HR with the request attached: copy it, or open it in the mail app. */
function HrMessage({ form, profile, onClose }: { form: RequestForm; profile: Profile; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const me = form.applicant === 'father' ? profile.father : profile.mother
  const period =
    form.start && form.end ? ` na okres od ${dotted(form.start)} do ${dotted(form.end)}` : form.start ? ` od ${dotted(form.start)}` : ''
  // The engine's e-mail (RequestForm.hr_message) with the placeholders filled in this browser.
  const filled = (text: string) =>
    text.replace(/\{\{([a-z0-9-]+)\}\}/g, (_, id: string) => {
      const field = form.letter?.fields.find((f) => f.id === id)
      if (field?.meaning === 'applicant-name') return me.name || '[imię i nazwisko]'
      if (field?.meaning === 'child-name') return profile.child.name || '[imię dziecka]'
      return '[…]'
    })
  const subject = form.hr_message ? filled(form.hr_message.subject) : form.title
  const body = form.hr_message
    ? filled(form.hr_message.body)
    : `Dzień dobry,\n\nw załączeniu przesyłam ${form.title.charAt(0).toLowerCase()}${form.title.slice(1)}${period}. ` +
      'Wniosek jest wypełniony i podpisany.\n\nProszę o potwierdzenie otrzymania.\n\nZ poważaniem\n' +
      (me.name || '[imię i nazwisko]')
  const mailto = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
  return (
    <motion.section
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.22, ease: EASE_OUT }}
      className="overflow-hidden"
      aria-label="Wiadomość do kadr"
    >
      <div className="mt-4 rounded-2xl border border-line px-4 py-3">
        <p className="text-xs font-bold text-navy-500">Temat: {subject}</p>
        <p className="mt-2 text-sm whitespace-pre-line text-navy-900">{body}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={async () => setCopied(await copyText(`${subject}\n\n${body}`))}
            className="flex h-9 items-center gap-2 rounded-full border border-line px-3.5 text-sm font-bold text-navy-700 hover:bg-navy-50"
          >
            {copied ? <Check className="size-4 text-zus-600" /> : <Mail className="size-4" />}
            {copied ? 'Skopiowano' : 'Kopiuj wiadomość'}
          </button>
          <a
            href={mailto}
            className="flex h-9 items-center gap-2 rounded-full bg-zus-600 px-3.5 text-sm font-bold text-white hover:bg-zus-700"
          >
            <Send className="size-4" /> Otwórz w poczcie
          </a>
          <button type="button" onClick={onClose} className="h-9 rounded-full px-3 text-sm font-bold text-navy-500 hover:bg-navy-50">
            Zamknij
          </button>
        </div>
        <p className="mt-2 text-xs text-navy-400">Pobrany wniosek (PDF) dołącz do wiadomości jako załącznik.</p>
      </div>
    </motion.section>
  )
}
