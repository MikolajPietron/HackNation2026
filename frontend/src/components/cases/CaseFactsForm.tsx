// The facts AI read from a case, to correct by hand (FUNKCJE: "wprowadzenie danych we własnym
// zakresie"): who applies, the birth, the insurance periods, the pay from Z-3, the decision of
// ZUS. "Przelicz" runs the calculator again on the corrected facts; no AI is involved.
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Trash2 } from 'lucide-react'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import { cn } from '@/lib/utils'
import type { CaseFacts, CaseOutcome, InsurancePeriod, InsuranceTitle, SicknessInsurance } from '@/types'

const TITLES: Record<InsuranceTitle, string> = {
  employment: 'umowa o pracę',
  contract: 'umowa zlecenia',
  business: 'działalność (JDG)',
  other: 'inny tytuł',
}
const SICKNESS: Record<SicknessInsurance, string> = {
  mandatory: 'chorobowe obowiązkowe',
  voluntary: 'chorobowe dobrowolne',
  none: 'bez chorobowego',
  unknown: 'nie wiadomo',
}
const OUTCOMES: Record<CaseOutcome, string> = {
  granted: 'przyznano',
  refused: 'odmowa',
  partial: 'przyznano częściowo',
  unknown: 'brak rozstrzygnięcia',
}

const INPUT =
  'h-10 w-full rounded-xl border border-line bg-white px-3 text-sm text-navy-900 outline-none transition-[border-color,box-shadow] focus:border-zus-400 focus:ring-4 focus:ring-zus-600/10'

export function CaseFactsForm({
  facts,
  busy,
  onRecalculate,
}: {
  facts: CaseFacts
  busy: boolean
  onRecalculate: (facts: CaseFacts) => void
}) {
  const [draft, setDraft] = useState(facts)
  const changed = JSON.stringify(draft) !== JSON.stringify(facts)
  const set = (patch: Partial<CaseFacts>) => setDraft({ ...draft, ...patch })
  const setPeriod = (index: number, patch: Partial<InsurancePeriod>) =>
    set({ insurance: draft.insurance.map((p, i) => (i === index ? { ...p, ...patch } : p)) })

  return (
    <div className="space-y-5 text-sm">
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Kto wnioskuje">
          <select
            className={INPUT}
            value={draft.applicant ?? 'mother'}
            onChange={(e) => set({ applicant: e.target.value as CaseFacts['applicant'] })}
          >
            <option value="mother">mama</option>
            <option value="father">tata</option>
          </select>
        </Field>
        <Field label="Data porodu">
          <input
            type="date"
            className={INPUT}
            value={draft.birth_date ?? ''}
            onChange={(e) => set({ birth_date: e.target.value || null, child_born: e.target.value ? true : draft.child_born })}
          />
        </Field>
        <Field label="Liczba dzieci">
          <input
            type="number"
            min={1}
            max={10}
            className={INPUT}
            value={draft.children_count ?? 1}
            onChange={(e) => set({ children_count: Math.max(1, Math.min(10, Number(e.target.value) || 1)) })}
          />
        </Field>
        <Field label="Decyzja ZUS">
          <select
            className={INPUT}
            value={draft.decision?.outcome ?? 'unknown'}
            onChange={(e) =>
              set({
                decision: {
                  benefit: draft.decision?.benefit ?? '',
                  reason: draft.decision?.reason ?? '',
                  pages: draft.decision?.pages ?? [],
                  outcome: e.target.value as CaseOutcome,
                },
              })
            }
          >
            {(Object.keys(OUTCOMES) as CaseOutcome[]).map((key) => (
              <option key={key} value={key}>
                {OUTCOMES[key]}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div>
        <p className="font-bold text-navy-900">Ubezpieczenie</p>
        {draft.insurance.length === 0 && <p className="mt-1 text-navy-500">AI nie odczytało okresów ubezpieczenia.</p>}
        <ul className="mt-2 space-y-2">
          {draft.insurance.map((period, index) => (
            <li key={index} className="grid gap-2 rounded-2xl bg-navy-50/60 p-2.5 sm:grid-cols-[110px_1fr_1fr_1fr_1fr_auto]">
              <select className={INPUT} value={period.person} onChange={(e) => setPeriod(index, { person: e.target.value as InsurancePeriod['person'] })}>
                <option value="mother">mama</option>
                <option value="father">tata</option>
              </select>
              <select className={INPUT} value={period.title} onChange={(e) => setPeriod(index, { title: e.target.value as InsuranceTitle })}>
                {(Object.keys(TITLES) as InsuranceTitle[]).map((key) => (
                  <option key={key} value={key}>
                    {TITLES[key]}
                  </option>
                ))}
              </select>
              <input type="date" aria-label="od" className={INPUT} value={period.start ?? ''} onChange={(e) => setPeriod(index, { start: e.target.value || null })} />
              <input type="date" aria-label="do" className={INPUT} value={period.end ?? ''} onChange={(e) => setPeriod(index, { end: e.target.value || null })} />
              <select className={INPUT} value={period.sickness} onChange={(e) => setPeriod(index, { sickness: e.target.value as SicknessInsurance })}>
                {(Object.keys(SICKNESS) as SicknessInsurance[]).map((key) => (
                  <option key={key} value={key}>
                    {SICKNESS[key]}
                  </option>
                ))}
              </select>
              <button
                type="button"
                aria-label="Usuń okres"
                onClick={() => set({ insurance: draft.insurance.filter((_, i) => i !== index) })}
                className="grid size-10 place-items-center rounded-xl text-navy-400 transition-colors hover:bg-white hover:text-alert-600"
              >
                <Trash2 className="size-4" />
              </button>
              <p className="text-xs text-navy-500 sm:col-span-6">
                {period.label}
                {period.pages.length > 0 && ` · s. ${period.pages.join(', ')}`}
              </p>
            </li>
          ))}
        </ul>
      </div>

      {draft.pay.length > 0 && (
        <div>
          <p className="font-bold text-navy-900">Wynagrodzenie i podstawa składek</p>
          <ul className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {draft.pay.map((month, index) => (
              <li key={`${month.person}-${month.month}-${index}`}>
                <label className="block text-xs font-bold text-navy-500">
                  {month.month}
                  {month.person === 'father' ? ' · tata' : ''}
                  {month.full_month === false ? ' · niepełny' : ''}
                </label>
                <input
                  type="number"
                  step="0.01"
                  className={cn(INPUT, 'mt-1 tabular-nums')}
                  value={month.amount}
                  onChange={(e) =>
                    set({
                      pay: draft.pay.map((m, i) => (i === index ? { ...m, amount: Number(e.target.value) || 0 } : m)),
                    })
                  }
                />
              </li>
            ))}
          </ul>
        </div>
      )}

      {draft.documents.length > 0 && (
        <div>
          <p className="font-bold text-navy-900">Dokumenty w aktach</p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {draft.documents.map((doc) => (
              <li key={`${doc.kind}-${doc.pages.join(',')}`} className="rounded-full bg-navy-50 px-2.5 py-1 text-xs font-bold text-navy-700">
                {doc.kind} · s. {doc.pages.join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-end">
        <PrimaryButton onClick={() => onRecalculate(draft)} disabled={!changed || busy} className="h-11 px-5 text-sm">
          Przelicz
        </PrimaryButton>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-bold text-navy-500">{label}</span>
      <span className="mt-1 block">{children}</span>
    </label>
  )
}
