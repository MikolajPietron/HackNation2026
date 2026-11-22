// "Twoje dane do wniosków": typed once, used in every request and in the folder. It stays in
// this browser (localStorage) and is never sent anywhere: the requests are made into PDF here.
// "Wypełnij z mObywatela" is a simulation, as the brief asks: the test account's made-up data.
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Lock, Trash2 } from 'lucide-react'
import { SimBadge } from '@/components/mocks/MockModal'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import type { Persona } from '@/lib/mockData'
import { clearProfile, fromMObywatel, useProfile, type Profile } from '@/lib/personal'
import type { Role } from '@/types'

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

  return (
    <form
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault()
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
        <Input value={draft.place} onChange={(place) => set('place', place)} placeholder="np. Warszawa" />
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
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="PESEL"
                value={p.pesel}
                onChange={(pesel) => set(pKey, { ...p, pesel: pesel.replace(/\D/g, '').slice(0, 11) })}
                inputMode="numeric"
              />
              <Input
                label="Nr konta do wypłaty zasiłku"
                value={p.account}
                onChange={(account) => set(pKey, { ...p, account })}
                inputMode="numeric"
              />
            </div>
            <Input
              label={`Pracodawca ${parent === 'mother' ? 'mamy' : 'taty'} — nazwa`}
              value={e.name}
              onChange={(name) => set(eKey, { ...e, name })}
              autoComplete="organization"
            />
            <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
              <Input label="Adres pracodawcy" value={e.address} onChange={(address) => set(eKey, { ...e, address })} />
              <Input label="NIP" value={e.nip} onChange={(nip) => set(eKey, { ...e, nip })} inputMode="numeric" />
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
            onChange={(pesel) => set('child', { ...draft.child, pesel: pesel.replace(/\D/g, '').slice(0, 11) })}
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
  value,
  onChange,
  placeholder,
  hint,
  inputMode,
  autoComplete,
}: {
  label?: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  hint?: string
  inputMode?: 'numeric' | 'text'
  autoComplete?: string
}) {
  return (
    <label className="block">
      {label && <span className="mb-1 block text-sm text-navy-700">{label}</span>}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        inputMode={inputMode}
        autoComplete={autoComplete}
        className="h-11 w-full rounded-xl border border-line bg-white px-3.5 text-navy-900 outline-none transition-[border-color,box-shadow] focus:border-zus-500 focus:ring-2 focus:ring-zus-100"
      />
      {hint && <span className="mt-1 block text-xs text-navy-400">{hint}</span>}
    </label>
  )
}
