// "Twoje dane z ZUS" after the simulated login (FUNKCJE F31–F34): insurance, contribution debt
// on the day the right arises, e-ZLA sick notes and a question to PUE/eZUS. All example data.
import type { ReactNode } from 'react'
import { FileCheck2, MessageSquare } from 'lucide-react'
import { ICONS } from '@/lib/icons'
import type { Persona } from '@/lib/mockData'
import { cn } from '@/lib/utils'
import { MockModal, SimBadge } from './MockModal'

export function ZusDataDialog({
  persona,
  open,
  onClose,
  onMock,
}: {
  persona: Persona | null
  open: boolean
  onClose: () => void
  onMock: (message: string) => void
}) {
  return (
    <MockModal open={open && persona !== null} label="Twoje dane z ZUS" onClose={onClose} className="max-w-xl">
      {persona && (
        <div className="text-navy-700">
          <div className="pr-10">
            <SimBadge />
            <h2 className="mt-3 text-2xl leading-tight font-bold tracking-tight text-navy-900">Twoje dane z ZUS</h2>
            <p className="mt-1 text-navy-500">{persona.name}</p>
          </div>

          <Section title="Ubezpieczenie chorobowe" icon={ICONS.parasol}>
            <Row label="Tytuł" value={persona.work} />
            <Row label="Chorobowe" value={persona.sickness} />
            <Row label="Kto wypłaca zasiłek" value={persona.payer} />
            <Row label="Podstawa składek" value={persona.contributionBase} />
          </Section>

          <Section title="Zadłużenie składkowe" icon={ICONS.pieniadze}>
            <div className="flex items-center gap-4">
              <p
                className={cn(
                  'text-2xl font-bold',
                  persona.debt.startsWith('0,00') ? 'text-zus-700' : 'text-alert-600',
                )}
              >
                {persona.debt}
              </p>
              <p className="flex-1 text-sm text-navy-500">
                {persona.debt.startsWith('0,00')
                  ? 'Brak zaległości na dzień powstania prawa.'
                  : 'Zaległość może wstrzymać prawo do zasiłku. Spłać ją przed porodem.'}
              </p>
              <SmallButton
                onClick={() => onMock('Zaświadczenie o niezaleganiu wygenerujemy w wersji demo.')}
              >
                <FileCheck2 className="size-4" /> Zaświadczenie
              </SmallButton>
            </div>
          </Section>

          <Section title="Zwolnienia lekarskie e-ZLA" icon={ICONS.zaswiadczenie}>
            {persona.ezla.length === 0 ? (
              <p className="text-navy-500">Brak zwolnień w ostatnich 12 miesiącach.</p>
            ) : (
              <ul className="space-y-2">
                {persona.ezla.map((z) => (
                  <li key={z.from} className="flex items-center gap-3">
                    <span className="rounded-lg bg-sun-100 px-2 py-0.5 text-xs font-black text-sun-700">
                      kod {z.code}
                    </span>
                    <span className="font-bold text-navy-900">
                      {z.from} – {z.to}
                    </span>
                    <span className="text-sm text-navy-500">{z.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <div className="mt-6 flex items-center gap-3 border-t border-line pt-5">
            <p className="flex-1 text-sm text-navy-500">Coś się nie zgadza? Zapytaj ZUS przez PUE/eZUS.</p>
            <SmallButton onClick={() => onMock('Pytanie do ZUS przez PUE/eZUS to atrapa integracji.')}>
              <MessageSquare className="size-4" /> Zadaj pytanie
            </SmallButton>
          </div>
        </div>
      )}
    </MockModal>
  )
}

function Section({ title, icon, children }: { title: string; icon: string; children: ReactNode }) {
  return (
    <section className="mt-6">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-bold text-navy-900">
        <img src={icon} alt="" draggable={false} className="size-8 object-contain" />
        {title}
      </h3>
      {children}
    </section>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-3 py-1">
      <span className="text-sm text-navy-500">{label}</span>
      <span className="font-bold text-navy-900">{value}</span>
    </div>
  )
}

export function SmallButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-line px-3.5 text-sm font-bold text-navy-900 transition-[border-color,background-color,transform] duration-150 hover:border-navy-200 hover:bg-navy-50 active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
    >
      {children}
    </button>
  )
}
