// The request filled in on the document itself, not in a list of inputs (decision of 22.11.2026:
// "jak formularze ZUS"). Two looks, as the brief tells them apart: a ZUS benefit form (ZAM, ZAS-53,
// "wnioski o świadczenia dostępne są na stronie www.zus.pl") as numbered boxes under the form's
// code, and a leave request to the employer ("wnioski o urlopy wymagają zaprojektowania") as the
// letter an employee writes, laid out like its PDF (lib/pdf/documents.ts). The fields, their order
// and every value are the engine's (`Document.form`); green ink marks what the plan filled in.
// What is wrong with a field shows right under it (`PaperCheck`, from ApplicationForm): the format
// checks of this browser and what "Sprawdź wniosek" found about that field.
import type { ReactNode } from 'react'
import { FieldError, type FieldIssue, type FieldTone } from '@/components/ui/field-error'
import { fieldLook } from '@/hooks/useFieldErrors'
import { formatLongDate } from '@/lib/dates'
import { applicantOf, type Profile } from '@/lib/personal'
import { cn } from '@/lib/utils'
import { formatAccount, peselDigits, typed } from '@/lib/validate'
import type { FormAttachment, FormField, RequestForm } from '@/types'

type Values = Record<string, string>

/** What the paper shows about each field, decided by ApplicationForm. */
export interface PaperCheck {
  /** The id of the field's message line, for `aria-describedby`. */
  id: (field: FormField) => string
  /** Everything to show under the field: format errors first, then the request check. */
  issues: (field: FormField) => FieldIssue[]
  /** How an input looks, by its value key (`field.id`, or `field.id:from` / `:to`). */
  tone: (key: string) => FieldTone | null
  /** The input was left: its format error shows from now on. */
  blur: (key: string) => void
}

/** What every input of a field gets from the check. */
interface Marked {
  tone?: FieldTone | null
  describedBy?: string
  onBlur?: () => void
}

function marked(check: PaperCheck, field: FormField, key: string): Marked {
  return {
    tone: check.tone(key),
    describedBy: check.issues(field).length > 0 ? check.id(field) : undefined,
    onBlur: () => check.blur(key),
  }
}

/** The worst tone under a field, for `data-issue` (ApplicationForm scrolls to the first one). */
function worst(issues: FieldIssue[]): FieldTone | undefined {
  if (issues.some((i) => i.tone === 'error')) return 'error'
  if (issues.some((i) => i.tone === 'warning')) return 'warning'
  return issues.length > 0 ? 'info' : undefined
}

/** The row of a field: marks it for scrolling, and the messages go right under its input. */
function FieldRow({
  check,
  field,
  as: Tag = 'div',
  className,
  children,
  after,
}: {
  check: PaperCheck
  field: FormField
  as?: 'div' | 'li'
  className?: string
  children: ReactNode
  /** Under the messages: hints that belong to the field. */
  after?: ReactNode
}) {
  const issues = check.issues(field)
  return (
    <Tag data-field={field.id} data-issue={worst(issues)} className={className}>
      {children}
      <FieldError id={check.id(field)} issues={issues} />
      {after}
    </Tag>
  )
}

/** Format while typing: the account in groups of digits, the child's PESEL digits only. */
const FORMATS: Record<string, (value: string) => string> = {
  'bank-account': formatAccount,
  'child-pesel': peselDigits,
}

interface PaperProps {
  form: RequestForm
  values: Values
  set: (key: string) => (value: string) => void
  profile: Profile
  saveProfile: (profile: Profile) => void
  attached: Set<string>
  toggle: (id: string) => void
  today: string
  /** Order the birth certificate (a simulation, F35), offered next to that attachment. */
  onCertificate?: () => void
  check: PaperCheck
}

export function RequestPaper(props: PaperProps) {
  return (
    <div className="mt-5">
      <p className="mb-2 flex items-center gap-2 text-xs text-navy-500">
        <span className="size-2 rounded-full bg-zus-600" aria-hidden />
        Na zielono: wpisane z Waszego planu. Puste pola uzupełnij na wniosku.
      </p>
      <div className="rounded-lg border border-navy-200 bg-white px-4 py-5 shadow-[0_18px_40px_-28px_rgb(26_36_56/0.45)] sm:px-7 sm:py-7">
        {props.form.official_form ? <ZusForm {...props} /> : <Letter {...props} />}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// A leave request: the letter to the employer

/** The applicant's own name field: it goes in the letter's header, as in the PDF. */
const headerNameField = (form: RequestForm) => form.fields.find((f) => f.personal && f.id.endsWith('-name'))

function Letter({ form, values, set, profile, saveProfile, attached, toggle, today, onCertificate, check }: PaperProps) {
  const { me, job } = applicantOf(form, profile)
  const roleKey = form.applicant === 'father' ? 'father' : 'mother'
  const jobKey = form.applicant === 'father' ? 'fatherEmployer' : 'motherEmployer'
  const nameField = headerNameField(form)
  const body = form.fields.filter((f) => f !== nameField)
  return (
    <div className="text-[14px] leading-relaxed text-navy-900">
      <p className="flex flex-wrap items-baseline justify-end">
        <Blank
          label="Miejscowość"
          value={profile.place}
          onChange={(place) => saveProfile({ ...profile, place })}
          placeholder="miejscowość"
          className="w-32 text-right"
        />
        <span>,&nbsp;{formatLongDate(today)} r.</span>
      </p>

      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        <div>
          {nameField ? (
            <FieldRow check={check} field={nameField}>
              <Blank
                label="Imię i nazwisko"
                value={values[nameField.id] ?? ''}
                onChange={set(nameField.id)}
                placeholder="imię i nazwisko"
                className="w-full font-bold"
                {...marked(check, nameField, nameField.id)}
              />
            </FieldRow>
          ) : (
            <Blank
              label="Imię i nazwisko"
              value={me.name}
              onChange={(name) => saveProfile({ ...profile, [roleKey]: { ...me, name } })}
              placeholder="imię i nazwisko"
              className="w-full font-bold"
            />
          )}
          <Blank
            label="Adres"
            value={me.address}
            onChange={(address) => saveProfile({ ...profile, [roleKey]: { ...me, address } })}
            placeholder="adres"
            className="mt-1 w-full"
          />
          <Caption>(imię i nazwisko, adres)</Caption>
        </div>
        <div className="sm:text-right">
          <Blank
            label="Pracodawca"
            value={job.name}
            onChange={(name) => saveProfile({ ...profile, [jobKey]: { ...job, name } })}
            placeholder="nazwa pracodawcy"
            className="w-full font-bold sm:text-right"
          />
          <Blank
            label="Adres pracodawcy"
            value={job.address}
            onChange={(address) => saveProfile({ ...profile, [jobKey]: { ...job, address } })}
            placeholder="adres pracodawcy"
            className="mt-1 w-full sm:text-right"
          />
          <Caption>({form.addressee_label.toLowerCase()})</Caption>
        </div>
      </div>

      <h3 className="mt-7 text-center text-[17px] font-black tracking-tight text-navy-900">{form.title}</h3>

      <div className="mt-5 space-y-4">
        {body.map((field) => (
          <FieldRow
            key={field.id}
            check={check}
            field={field}
            after={field.hint && <p className="mt-1 text-xs text-navy-400">{field.hint}</p>}
          >
            <p className="text-[13px] text-navy-500">
              {field.label}
              {!field.required && <span className="text-navy-400"> (jeśli dotyczy)</span>}
            </p>
            <LetterValue field={field} values={values} set={set} check={check} />
          </FieldRow>
        ))}
      </div>

      <Attachments form={form} attached={attached} toggle={toggle} onCertificate={onCertificate} />

      <div className="mt-8 ml-auto w-52 text-center">
        <div className="border-b border-dotted border-navy-400 pb-6" aria-hidden />
        <Caption>(podpis)</Caption>
      </div>
    </div>
  )
}

function LetterValue({
  field,
  values,
  set,
  check,
}: {
  field: FormField
  values: Values
  set: PaperProps['set']
  check: PaperCheck
}) {
  const plan = fromPlan(field)
  if (field.kind === 'period') {
    const from = `${field.id}:from`
    const to = `${field.id}:to`
    return (
      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2">
        od
        <DateBlank label={`${field.label}: od`} value={values[from] ?? ''} onChange={set(from)} plan={plan} {...marked(check, field, from)} />
        do
        <DateBlank label={`${field.label}: do`} value={values[to] ?? ''} onChange={set(to)} plan={plan} {...marked(check, field, to)} />
      </p>
    )
  }
  if (field.kind === 'date') {
    return (
      <DateBlank
        label={field.label}
        value={values[field.id] ?? ''}
        onChange={set(field.id)}
        plan={plan}
        className="mt-0.5"
        {...marked(check, field, field.id)}
      />
    )
  }
  if (field.kind === 'statement') {
    return (
      <Lines label={field.label} value={values[field.id] ?? ''} onChange={set(field.id)} plan={plan} {...marked(check, field, field.id)} />
    )
  }
  return (
    <Blank
      label={field.label}
      value={values[field.id] ?? ''}
      onChange={set(field.id)}
      placeholder={field.personal ? 'wpisz' : ''}
      personal={field.personal}
      format={FORMATS[field.id]}
      className={cn('mt-0.5 w-full', plan && 'text-zus-700')}
      {...marked(check, field, field.id)}
    />
  )
}

// ---------------------------------------------------------------------------------------------
// A ZUS benefit form: numbered boxes under the form's code

function ZusForm({ form, values, set, attached, toggle, onCertificate, check }: PaperProps) {
  const title = form.title.replace(/\s*\([^)]*\)\s*$/, '')
  return (
    <div className="text-navy-900">
      <header className="flex items-stretch gap-3 border-b-2 border-navy-900 pb-3">
        <span className="grid place-items-center border-2 border-navy-900 px-3 text-2xl leading-none font-black tracking-tight">
          {form.official_form}
        </span>
        <div className="min-w-0">
          <p className="text-[10px] font-bold tracking-wider text-navy-500 uppercase">
            Formularz ZUS · oficjalny wzór na www.zus.pl
          </p>
          <p className="mt-0.5 text-[15px] leading-snug font-black uppercase">{title}</p>
          <p className="text-xs text-navy-500">Składasz: {form.addressee_label}</p>
        </div>
      </header>

      <ol className="mt-1">
        {form.fields.map((field, index) => (
          <li key={field.id} className="grid grid-cols-[1.75rem_1fr] gap-x-1 border-b border-navy-100 py-3 last:border-b-0">
            <span className="pt-0.5 text-xs font-black text-navy-400 tabular-nums">{index + 1}.</span>
            <FieldRow
              check={check}
              field={field}
              className="min-w-0"
              after={
                <>
                  {field.kind === 'period' && field.value && (
                    <p className="mt-1 text-xs text-navy-400">Na osi: {field.value}</p>
                  )}
                  {field.hint && <p className="mt-1 text-xs text-navy-400">{field.hint}</p>}
                </>
              }
            >
              <p className="text-[12.5px] leading-snug text-navy-700">
                {field.label}
                {!field.required && <span className="text-navy-400"> (jeśli dotyczy)</span>}
              </p>
              <div className="mt-1.5">
                <BoxValue field={field} values={values} set={set} check={check} />
              </div>
            </FieldRow>
          </li>
        ))}
      </ol>

      <Attachments form={form} attached={attached} toggle={toggle} onCertificate={onCertificate} />
    </div>
  )
}

/** A question the form answers with a tick: "Czy …", but not "czy …, czy …" (two choices). */
const yesNo = (field: FormField) =>
  field.value === null && /^Czy\s/.test(field.label) && !/,\s*czy\s/i.test(field.label)

function BoxValue({
  field,
  values,
  set,
  check,
}: {
  field: FormField
  values: Values
  set: PaperProps['set']
  check: PaperCheck
}) {
  const plan = fromPlan(field)
  if (yesNo(field)) {
    const value = values[field.id] ?? ''
    const { tone, describedBy } = marked(check, field, field.id)
    return (
      <div
        role="radiogroup"
        aria-label={field.label}
        aria-invalid={tone === 'error' ? true : undefined}
        aria-describedby={describedBy}
        className="flex gap-5"
      >
        {(['tak', 'nie'] as const).map((answer) => (
          <label key={answer} className="flex cursor-pointer items-center gap-2 text-sm font-bold">
            <input
              type="radio"
              name={field.id}
              checked={value === answer}
              onChange={() => set(field.id)(answer)}
              className="peer sr-only"
            />
            <span
              className={cn(
                'grid size-5 place-items-center border-2 border-navy-700 text-[13px] leading-none font-black transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-zus-400',
                tone === 'error' && 'border-alert-600',
                tone === 'warning' && 'border-sun-400',
                value === answer && 'bg-white text-zus-700',
              )}
              aria-hidden
            >
              {value === answer ? '✕' : ''}
            </span>
            {answer.toUpperCase()}
          </label>
        ))}
      </div>
    )
  }
  if (field.kind === 'period') {
    const from = `${field.id}:from`
    const to = `${field.id}:to`
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-navy-500">od</span>
        <Box label={`${field.label}: od`} value={values[from] ?? ''} onChange={set(from)} plan={plan} date {...marked(check, field, from)} />
        <span className="text-navy-500">do</span>
        <Box label={`${field.label}: do`} value={values[to] ?? ''} onChange={set(to)} plan={plan} date {...marked(check, field, to)} />
      </div>
    )
  }
  if (field.kind === 'date') {
    return (
      <Box label={field.label} value={values[field.id] ?? ''} onChange={set(field.id)} plan={plan} date {...marked(check, field, field.id)} />
    )
  }
  if (/pesel/.test(field.id)) {
    return (
      <Cells
        label={field.label}
        value={values[field.id] ?? ''}
        onChange={set(field.id)}
        count={11}
        format={FORMATS[field.id]}
        {...marked(check, field, field.id)}
      />
    )
  }
  return (
    <Box
      label={field.label}
      value={values[field.id] ?? ''}
      onChange={set(field.id)}
      plan={plan}
      multiline={field.kind === 'statement' || (values[field.id] ?? '').length > 48}
      format={FORMATS[field.id]}
      numeric={field.id === 'bank-account' || /nip/.test(field.id)}
      {...marked(check, field, field.id)}
    />
  )
}

// ---------------------------------------------------------------------------------------------
// Pieces

/** What the plan filled in (not personal data, which the parent types). */
const fromPlan = (field: FormField) => !field.personal && (field.value !== null || field.start !== null)

function Caption({ children }: { children: ReactNode }) {
  return <p className="mt-0.5 text-[11px] text-navy-400">{children}</p>
}

/** A blank on a dotted line, as on paper; with an issue the line turns solid red (or amber). */
function Blank({
  label,
  value,
  onChange,
  placeholder,
  personal,
  format,
  className,
  tone,
  describedBy,
  onBlur,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  personal?: boolean
  format?: (value: string) => string
  className?: string
} & Marked) {
  return (
    <input
      aria-label={label}
      value={value}
      onChange={(e) => onChange(typed(e.target, format))}
      onBlur={onBlur}
      aria-invalid={tone === 'error' ? true : undefined}
      aria-describedby={describedBy}
      placeholder={placeholder}
      autoComplete={personal ? 'off' : undefined}
      className={cn(
        'block h-8 min-w-0 rounded-sm border-0 border-b border-dotted border-navy-400 bg-transparent px-0.5 outline-none transition-[background-color,border-color] duration-150 placeholder:font-normal placeholder:text-navy-300 hover:bg-navy-50/60 focus:border-solid focus:border-zus-600 focus:bg-sun-100/50',
        tone && tone !== 'info' && 'border-solid',
        fieldLook(tone),
        className,
      )}
    />
  )
}

function DateBlank({
  label,
  value,
  onChange,
  plan,
  className,
  ...mark
}: {
  label: string
  value: string
  onChange: (value: string) => void
  plan: boolean
  className?: string
} & Marked) {
  return (
    <Blank
      label={label}
      value={value}
      onChange={onChange}
      placeholder="DD.MM.RRRR"
      className={cn('inline-block w-28 text-center font-bold tabular-nums', plan && 'text-zus-700', className)}
      {...mark}
    />
  )
}

/** A longer answer written on ruled lines; with an issue the lines turn red (or amber). */
function Lines({
  label,
  value,
  onChange,
  plan,
  tone,
  describedBy,
  onBlur,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  plan: boolean
} & Marked) {
  const line = tone === 'error' ? 'var(--color-alert-600)' : tone === 'warning' ? 'var(--color-sun-400)' : 'var(--color-navy-300)'
  return (
    <textarea
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      aria-invalid={tone === 'error' ? true : undefined}
      aria-describedby={describedBy}
      rows={2}
      className={cn(
        'mt-0.5 block w-full resize-y border-0 bg-transparent px-0.5 leading-8 outline-none focus:bg-sun-100/40',
        plan && 'text-zus-700',
      )}
      style={{
        backgroundImage: `repeating-linear-gradient(to bottom, transparent 0, transparent calc(2rem - 1px), ${line} calc(2rem - 1px), ${line} 2rem)`,
        backgroundAttachment: 'local',
      }}
    />
  )
}

/** A box of a ZUS form; with an issue its border turns red (or amber). */
function Box({
  label,
  value,
  onChange,
  plan,
  date,
  multiline,
  numeric,
  format,
  tone,
  describedBy,
  onBlur,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  plan: boolean
  date?: boolean
  multiline?: boolean
  numeric?: boolean
  format?: (value: string) => string
} & Marked) {
  const look = cn(
    'block rounded-[3px] border border-navy-300 bg-white px-2.5 text-sm outline-none transition-[border-color,box-shadow] duration-150 focus:border-zus-600 focus:ring-2 focus:ring-zus-600/15',
    plan ? 'font-bold text-zus-700' : 'text-navy-900',
    fieldLook(tone),
  )
  const aria = {
    'aria-label': label,
    'aria-invalid': tone === 'error' ? true : undefined,
    'aria-describedby': describedBy,
  }
  if (multiline) {
    return (
      <textarea
        {...aria}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        rows={2}
        className={cn(look, 'w-full resize-y py-2 leading-relaxed')}
      />
    )
  }
  return (
    <input
      {...aria}
      value={value}
      onChange={(e) => onChange(typed(e.target, format))}
      onBlur={onBlur}
      placeholder={date ? 'DD.MM.RRRR' : undefined}
      inputMode={date || numeric ? 'numeric' : undefined}
      autoComplete={numeric ? 'off' : undefined}
      className={cn(
        look,
        'h-9 placeholder:text-navy-300',
        date ? 'w-32 text-center tabular-nums' : 'w-full',
        numeric && 'tabular-nums',
      )}
    />
  )
}

/** One character per box, as PESEL is written on ZUS forms. */
function Cells({
  label,
  value,
  onChange,
  count,
  format = (text: string) => text.replace(/\s/g, ''),
  tone,
  describedBy,
  onBlur,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  count: number
  /** No hard limit by default: the ZAM row also takes a passport number when there is no PESEL. */
  format?: (value: string) => string
} & Marked) {
  // Monospace: 1ch is one character, so each sits in its own 2.2ch box.
  return (
    <input
      aria-label={label}
      value={value}
      onChange={(e) => onChange(typed(e.target, format))}
      onBlur={onBlur}
      aria-invalid={tone === 'error' ? true : undefined}
      aria-describedby={describedBy}
      inputMode="numeric"
      autoComplete="off"
      className={cn(
        'block h-9 rounded-[3px] border border-navy-300 bg-white font-mono text-base text-navy-900 outline-none transition-[border-color,box-shadow] duration-150 focus:border-zus-600 focus:ring-2 focus:ring-zus-600/15',
        fieldLook(tone),
      )}
      style={{
        width: `calc(${count} * 2.2ch + 2px)`,
        paddingLeft: '0.6ch',
        letterSpacing: '1.2ch',
        backgroundImage:
          'repeating-linear-gradient(to right, transparent 0, transparent calc(2.2ch - 1px), var(--color-navy-200) calc(2.2ch - 1px), var(--color-navy-200) 2.2ch)',
      }}
    />
  )
}

function Attachments({
  form,
  attached,
  toggle,
  onCertificate,
}: {
  form: RequestForm
  attached: Set<string>
  toggle: (id: string) => void
  onCertificate?: () => void
}) {
  if (form.attachments.length === 0) return null
  return (
    <section className="mt-6">
      <h4 className="text-sm font-bold text-navy-900">Załączniki</h4>
      <p className="text-xs text-navy-500">Zaznacz to, co już masz.</p>
      <ul className="mt-2 space-y-1.5">
        {form.attachments.map((attachment: FormAttachment) => {
          const on = attached.has(attachment.id)
          return (
            <li key={attachment.id}>
              <label className="flex cursor-pointer items-start gap-2.5 text-sm">
                <input type="checkbox" checked={on} onChange={() => toggle(attachment.id)} className="peer sr-only" />
                <span
                  className="mt-0.5 grid size-4.5 shrink-0 place-items-center border-2 border-navy-700 text-[12px] leading-none font-black text-zus-700 peer-focus-visible:ring-2 peer-focus-visible:ring-zus-400"
                  aria-hidden
                >
                  {on ? '✕' : ''}
                </span>
                <span className="min-w-0">
                  {attachment.label}
                  {!attachment.required && <span className="text-navy-400"> (jeśli dotyczy)</span>}
                  {attachment.hint && <span className="block text-xs text-navy-500">{attachment.hint}</span>}
                </span>
              </label>
              {onCertificate && !on && /aktu urodzenia/i.test(attachment.label) && (
                <button
                  type="button"
                  onClick={onCertificate}
                  className="mt-0.5 ml-7 text-xs font-bold text-zus-700 hover:text-zus-900"
                >
                  Nie masz? Zamów odpis (symulacja)
                </button>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
