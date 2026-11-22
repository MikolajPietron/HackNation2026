// The request filled in on the document itself, not in a list of inputs (decision of 22.11.2026:
// "jak formularze ZUS"). Two looks, as the brief tells them apart: a ZUS benefit form (ZAM, ZAS-53,
// "wnioski o świadczenia dostępne są na stronie www.zus.pl") as numbered boxes under the form's
// code, and a leave request to the employer ("wnioski o urlopy wymagają zaprojektowania") as the
// letter an employee writes, laid out like its PDF (lib/pdf/documents.ts). The fields, their order
// and every value are the engine's (`Document.form`); green ink marks what the plan filled in.
import type { ReactNode } from 'react'
import { formatLongDate } from '@/lib/dates'
import { applicantOf, type Profile } from '@/lib/personal'
import { cn } from '@/lib/utils'
import type { FormAttachment, FormField, RequestForm } from '@/types'

type Values = Record<string, string>

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

function Letter({ form, values, set, profile, saveProfile, attached, toggle, today, onCertificate }: PaperProps) {
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
          <Blank
            label="Imię i nazwisko"
            value={nameField ? (values[nameField.id] ?? '') : me.name}
            onChange={nameField ? set(nameField.id) : (name) => saveProfile({ ...profile, [roleKey]: { ...me, name } })}
            placeholder="imię i nazwisko"
            className="w-full font-bold"
          />
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
          <div key={field.id}>
            <p className="text-[13px] text-navy-500">
              {field.label}
              {!field.required && <span className="text-navy-400"> (jeśli dotyczy)</span>}
            </p>
            <LetterValue field={field} values={values} set={set} />
            {field.hint && <p className="mt-1 text-xs text-navy-400">{field.hint}</p>}
          </div>
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

function LetterValue({ field, values, set }: { field: FormField; values: Values; set: PaperProps['set'] }) {
  const plan = fromPlan(field)
  if (field.kind === 'period') {
    return (
      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2">
        od
        <DateBlank label={`${field.label}: od`} value={values[`${field.id}:from`] ?? ''} onChange={set(`${field.id}:from`)} plan={plan} />
        do
        <DateBlank label={`${field.label}: do`} value={values[`${field.id}:to`] ?? ''} onChange={set(`${field.id}:to`)} plan={plan} />
      </p>
    )
  }
  if (field.kind === 'date') {
    return <DateBlank label={field.label} value={values[field.id] ?? ''} onChange={set(field.id)} plan={plan} className="mt-0.5" />
  }
  if (field.kind === 'statement') {
    return <Lines label={field.label} value={values[field.id] ?? ''} onChange={set(field.id)} plan={plan} />
  }
  return (
    <Blank
      label={field.label}
      value={values[field.id] ?? ''}
      onChange={set(field.id)}
      placeholder={field.personal ? 'wpisz' : ''}
      personal={field.personal}
      className={cn('mt-0.5 w-full', plan && 'text-zus-700')}
    />
  )
}

// ---------------------------------------------------------------------------------------------
// A ZUS benefit form: numbered boxes under the form's code

function ZusForm({ form, values, set, attached, toggle, onCertificate }: PaperProps) {
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
            <div className="min-w-0">
              <p className="text-[12.5px] leading-snug text-navy-700">
                {field.label}
                {!field.required && <span className="text-navy-400"> (jeśli dotyczy)</span>}
              </p>
              <div className="mt-1.5">
                <BoxValue field={field} values={values} set={set} />
              </div>
              {field.kind === 'period' && field.value && (
                <p className="mt-1 text-xs text-navy-400">Na osi: {field.value}</p>
              )}
              {field.hint && <p className="mt-1 text-xs text-navy-400">{field.hint}</p>}
            </div>
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

function BoxValue({ field, values, set }: { field: FormField; values: Values; set: PaperProps['set'] }) {
  const plan = fromPlan(field)
  if (yesNo(field)) {
    const value = values[field.id] ?? ''
    return (
      <div role="radiogroup" aria-label={field.label} className="flex gap-5">
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
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-navy-500">od</span>
        <Box label={`${field.label}: od`} value={values[`${field.id}:from`] ?? ''} onChange={set(`${field.id}:from`)} plan={plan} date />
        <span className="text-navy-500">do</span>
        <Box label={`${field.label}: do`} value={values[`${field.id}:to`] ?? ''} onChange={set(`${field.id}:to`)} plan={plan} date />
      </div>
    )
  }
  if (field.kind === 'date') {
    return <Box label={field.label} value={values[field.id] ?? ''} onChange={set(field.id)} plan={plan} date />
  }
  if (/pesel/.test(field.id)) {
    return <Cells label={field.label} value={values[field.id] ?? ''} onChange={set(field.id)} count={11} />
  }
  return (
    <Box
      label={field.label}
      value={values[field.id] ?? ''}
      onChange={set(field.id)}
      plan={plan}
      multiline={field.kind === 'statement' || (values[field.id] ?? '').length > 48}
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

/** A blank on a dotted line, as on paper. */
function Blank({
  label,
  value,
  onChange,
  placeholder,
  personal,
  className,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  personal?: boolean
  className?: string
}) {
  return (
    <input
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoComplete={personal ? 'off' : undefined}
      className={cn(
        'block h-8 min-w-0 rounded-sm border-0 border-b border-dotted border-navy-400 bg-transparent px-0.5 outline-none transition-[background-color,border-color] duration-150 placeholder:font-normal placeholder:text-navy-300 hover:bg-navy-50/60 focus:border-solid focus:border-zus-600 focus:bg-sun-100/50',
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
}: {
  label: string
  value: string
  onChange: (value: string) => void
  plan: boolean
  className?: string
}) {
  return (
    <Blank
      label={label}
      value={value}
      onChange={onChange}
      placeholder="DD.MM.RRRR"
      className={cn('inline-block w-28 text-center font-bold tabular-nums', plan && 'text-zus-700', className)}
    />
  )
}

/** A longer answer written on ruled lines. */
function Lines({
  label,
  value,
  onChange,
  plan,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  plan: boolean
}) {
  return (
    <textarea
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={2}
      className={cn(
        'mt-0.5 block w-full resize-y border-0 bg-transparent px-0.5 leading-8 outline-none focus:bg-sun-100/40',
        plan && 'text-zus-700',
      )}
      style={{
        backgroundImage:
          'repeating-linear-gradient(to bottom, transparent 0, transparent calc(2rem - 1px), var(--color-navy-300) calc(2rem - 1px), var(--color-navy-300) 2rem)',
        backgroundAttachment: 'local',
      }}
    />
  )
}

/** A box of a ZUS form. */
function Box({
  label,
  value,
  onChange,
  plan,
  date,
  multiline,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  plan: boolean
  date?: boolean
  multiline?: boolean
}) {
  const look = cn(
    'block rounded-[3px] border border-navy-300 bg-white px-2.5 text-sm outline-none transition-[border-color,box-shadow] duration-150 focus:border-zus-600 focus:ring-2 focus:ring-zus-600/15',
    plan ? 'font-bold text-zus-700' : 'text-navy-900',
  )
  if (multiline) {
    return (
      <textarea
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={2}
        className={cn(look, 'w-full resize-y py-2 leading-relaxed')}
      />
    )
  }
  return (
    <input
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={date ? 'DD.MM.RRRR' : undefined}
      inputMode={date ? 'numeric' : undefined}
      className={cn(look, 'h-9 placeholder:text-navy-300', date ? 'w-32 text-center tabular-nums' : 'w-full')}
    />
  )
}

/** One character per box, as PESEL is written on ZUS forms. */
function Cells({
  label,
  value,
  onChange,
  count,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  count: number
}) {
  // Monospace: 1ch is one character, so each sits in its own 2.2ch box.
  return (
    <input
      aria-label={label}
      value={value}
      // No hard limit: the ZAM row also takes a passport number when there is no PESEL.
      onChange={(e) => onChange(e.target.value.replace(/\s/g, ''))}
      inputMode="numeric"
      autoComplete="off"
      className="block h-9 rounded-[3px] border border-navy-300 bg-white font-mono text-base text-navy-900 outline-none focus:border-zus-600 focus:ring-2 focus:ring-zus-600/15"
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
