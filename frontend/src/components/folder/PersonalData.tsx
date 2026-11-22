// "Twoje dane do wniosków": typed once, used in every request and in the folder. It stays in
// this browser (localStorage) and is never sent anywhere: the requests are made into PDF here.
// "Wypełnij z mObywatela" is a simulation, as the brief asks: the test account's made-up data.
// PESEL, the bank account and NIP are checked here, in the browser (lib/validate.ts): the error
// shows under the field once it is left, and "Zapisz dane" with an error goes to that field.
import { useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useReducedMotion } from 'motion/react'
import { Lock, Trash2 } from 'lucide-react'
import { SimBadge } from '@/components/mocks/MockModal'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import { FieldError } from '@/components/ui/field-error'
import { fieldLook, useFieldErrors } from '@/hooks/useFieldErrors'
import type { Persona } from '@/lib/mockData'
import { clearProfile, fromMObywatel, useProfile, type Profile } from '@/lib/personal'
import { accountError, formatAccount, nipError, peselDigits, peselError, typed } from '@/lib/validate'
import { cn } from '@/lib/utils'
import type { Role } from '@/types'

type Validate = (value: string) => string | null

export function PersonalData({
  role,
  withFather,
  persona,
  onLogin,
  onDone,
}: {
  /** Who fills in the interview: their data first, and the one mObywatel fills. */
  role: Role
  /** The father has his own requests (his leave on the timeline). */
  withFather: boolean
  persona: Persona | null
  onLogin: () => void
  onDone: () => void
}) {
  const [saved, save] = useProfile()
  const [draft, setDraft] = useState<Profile>(saved)
  const set = <K extends keyof Profile>(key: K, value: Profile[K]) => setDraft((d) => ({ ...d, [key]: value }))

  const fill = () => {
    if (!persona) return onLogin()
    const employerName = persona.payer.split(' — ')[0]
    setDraft((d) => fromMObywatel(d, persona.name, employerName, role))
  }

  const parents: Role[] = withFather || role === 'father' ? ['mother', 'father'] : ['mother']
  const ordered = role === 'father' ? [...parents].reverse() : parents

  // The fields with a format, in their order on screen (only the parents shown are checked).
  const rules: { key: string; value: string; validate: Validate }[] = [
    ...ordered.flatMap((parent) => {
      const e = parent === 'mother' ? 'motherEmployer' : 'fatherEmployer'
      return [
        { key: `${parent}.pesel`, value: draft[parent].pesel, validate: peselError },
        { key: `${parent}.account`, value: draft[parent].account, validate: accountError },
        { key: `${e}.nip`, value: draft[e].nip, validate: nipError },
      ]
    }),
    { key: 'child.pesel', value: draft.child.pesel, validate: peselError },
  ]
  const errors = useFieldErrors()
  const inputs = useRef(new Map<string, HTMLInputElement>())
  const reduce = useReducedMotion()

  /** The props of a field with a format: its error, blur and the ref to go back to it. */
  const checked = (key: string, update: (value: string) => void) => {
    const rule = rules.find((r) => r.key === key)!
    return {
      error: errors.shown(key, rule.validate(rule.value)),
      onBlur: () => errors.blur(key, rule.validate(rule.value)),
      onChange: (value: string) => {
        update(value)
        errors.change(key, rule.validate(value))
      },
      inputRef: (element: HTMLInputElement | null) => {
        if (element) inputs.current.set(key, element)
        else inputs.current.delete(key)
      },
    }
  }

  return (
    <form
      className="space-y-6"
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        const failing = rules.filter((r) => r.validate(r.value)).map((r) => r.key)
        if (failing.length > 0) {
          // Nothing is saved: each wrong field says why, and the first one is brought into view.
          errors.showAll(failing)
          const first = inputs.current.get(failing[0])
          first?.focus({ preventScroll: true })
          first?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' })
          return
        }
        save(draft)
        onDone()
      }}
    >
      <h2 className="pr-10 text-2xl font-bold tracking-tight text-navy-900">Twoje dane do wniosków</h2>
      <p className="flex gap-2.5 rounded-2xl bg-zus-50 px-4 py-3 text-sm text-zus-900">
        <Lock className="mt-0.5 size-4 shrink-0" />
        Wpisz raz — trafią do wszystkich wniosków. Zostają tylko w tej przeglądarce: nie wysyłamy ich na serwer
        ani do AI, a wnioski w PDF powstają na Twoim urządzeniu.
      </p>

      <button
        type="button"
        onClick={fill}
        className="flex w-full items-center justify-between gap-3 rounded-2xl border border-line px-4 py-3 text-left transition-colors hover:bg-navy-50/60"
      >
        <span>
          <span className="block font-bold text-navy-900">Wypełnij z mObywatela</span>
          <span className="block text-sm text-navy-500">
            {persona ? `Konto testowe: ${persona.name}` : 'Najpierw zaloguj się (symulacja)'}
          </span>
        </span>
        <SimBadge>symulacja</SimBadge>
      </button>

      <Group title="Miejscowość (do daty na wniosku)">
        <Input
          ariaLabel="Miejscowość"
          value={draft.place}
          onChange={(place) => set('place', place)}
          placeholder="np. Warszawa"
        />
      </Group>

      {ordered.map((parent) => {
        const p = parent === 'mother' ? draft.mother : draft.father
        const e = parent === 'mother' ? draft.motherEmployer : draft.fatherEmployer
        const pKey = parent === 'mother' ? 'mother' : 'father'
        const eKey = parent === 'mother' ? 'motherEmployer' : 'fatherEmployer'
        return (
          <Group key={parent} title={parent === 'mother' ? 'Mama' : 'Tata'}>
            <Input label="Imię i nazwisko" value={p.name} onChange={(name) => set(pKey, { ...p, name })} autoComplete="name" />
            <Input
              label="Adres"
              value={p.address}
              onChange={(address) => set(pKey, { ...p, address })}
              autoComplete="street-address"
            />
            <div className="grid gap-3 sm:grid-cols-[10.5rem_1fr]">
              <Input
                label="PESEL"
                value={p.pesel}
                {...checked(`${pKey}.pesel`, (pesel) => set(pKey, { ...p, pesel }))}
                format={peselDigits}
                inputMode="numeric"
              />
              <Input
                label="Nr konta do wypłaty zasiłku"
                value={p.account}
                {...checked(`${pKey}.account`, (account) => set(pKey, { ...p, account }))}
                format={formatAccount}
                placeholder="00 0000 0000 0000 0000 0000 0000"
                inputMode="numeric"
              />
            </div>
            <Input
              label={`Pracodawca ${parent === 'mother' ? 'mamy' : 'taty'} — nazwa`}
              value={e.name}
              onChange={(name) => set(eKey, { ...e, name })}
              autoComplete="organization"
            />
            <div className="grid gap-3 sm:grid-cols-[1fr_13rem]">
              <Input label="Adres pracodawcy" value={e.address} onChange={(address) => set(eKey, { ...e, address })} />
              <Input
                label="NIP"
                value={e.nip}
                {...checked(`${eKey}.nip`, (nip) => set(eKey, { ...e, nip }))}
                inputMode="numeric"
              />
            </div>
          </Group>
        )
      })}

      <Group title="Dziecko">
        <Input
          label="Imię i nazwisko"
          value={draft.child.name}
          onChange={(name) => set('child', { ...draft.child, name })}
          hint="Jeśli dziecko jeszcze się nie urodziło, zostaw puste."
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="PESEL dziecka"
            value={draft.child.pesel}
            {...checked('child.pesel', (pesel) => set('child', { ...draft.child, pesel }))}
            format={peselDigits}
            inputMode="numeric"
          />
          <Input
            label="Miejsce urodzenia"
            value={draft.child.birthPlace}
            onChange={(birthPlace) => set('child', { ...draft.child, birthPlace })}
          />
        </div>
      </Group>

      <div className="flex flex-wrap items-center gap-3 pt-1">
        <PrimaryButton type="submit" className="h-12 px-6 text-base">
          Zapisz dane
        </PrimaryButton>
        <button
          type="button"
          onClick={() => {
            clearProfile()
            onDone()
          }}
          className="flex h-12 items-center gap-2 rounded-full px-4 text-sm font-bold text-navy-500 hover:bg-navy-50 hover:text-navy-900"
        >
          <Trash2 className="size-4" /> Usuń z tej przeglądarki
        </button>
      </div>
    </form>
  )
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-3">
      <legend className="mb-2 text-sm font-bold text-navy-500">{title}</legend>
      {children}
    </fieldset>
  )
}

function Input({
  label,
  ariaLabel,
  value,
  onChange,
  format,
  error,
  onBlur,
  inputRef,
  placeholder,
  hint,
  inputMode,
  autoComplete,
}: {
  label?: string
  /** The name when there is no visible label. */
  ariaLabel?: string
  value: string
  onChange: (value: string) => void
  /** Reformats what is typed (digits only, the account in groups), keeping the caret in place. */
  format?: (value: string) => string
  /** The format error to show under the field. */
  error?: string | null
  onBlur?: () => void
  inputRef?: (element: HTMLInputElement | null) => void
  placeholder?: string
  hint?: string
  inputMode?: 'numeric' | 'text'
  autoComplete?: string
}) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const describedBy = [error && errorId, hint && hintId].filter(Boolean).join(' ') || undefined
  return (
    <div>
      {label && (
        <label htmlFor={id} className="mb-1 block text-sm text-navy-700">
          {label}
        </label>
      )}
      <input
        id={id}
        ref={inputRef}
        value={value}
        onChange={(event) => onChange(typed(event.target, format))}
        onBlur={onBlur}
        placeholder={placeholder}
        inputMode={inputMode}
        autoComplete={autoComplete}
        aria-label={label ? undefined : ariaLabel}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(
          'h-11 w-full rounded-xl border border-line bg-white px-3.5 text-navy-900 outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-navy-300 focus:border-zus-600 focus:ring-2 focus:ring-zus-600/15',
          inputMode === 'numeric' && 'tabular-nums',
          fieldLook(error ? 'error' : null),
        )}
      />
      <FieldError id={errorId} issues={error ? [{ key: 'format', tone: 'error', text: error }] : []} />
      {hint && (
        <span id={hintId} className="mt-1 block text-xs text-navy-400">
          {hint}
        </span>
      )}
    </div>
  )
}
