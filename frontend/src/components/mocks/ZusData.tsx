// "Twoje dane z ZUS" after the simulated login (FUNKCJE F31–F34): insurance, contribution debt
// on the day the right arises, e-ZLA sick notes and a question to PUE/eZUS. All example data.
// The brief asks to simulate issuing the debt certificate and its amount (guide page 13): the
// certificate is an example document, and its amount can go into the plan, where the engine says
// what it means for the benefit (engine/debt.py, ustawa art. 2a).
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, ChevronRight, FileCheck2, LoaderCircle, MessageSquare } from 'lucide-react'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import { Emphasis } from '@/components/ui/emphasis'
import { Illustration } from '@/components/ui/illustration'
import type { PlanApply } from '@/hooks/usePlanChange'
import { formatLongDate, todayIso } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import type { Persona } from '@/lib/mockData'
import { formatPln } from '@/lib/money'
import { cn } from '@/lib/utils'
import type { Role, Scenario, Timeline } from '@/types'
import { MockModal, SimBadge } from './MockModal'

type View = 'data' | 'issuing' | 'certificate'

export function ZusDataDialog({
  persona,
  open,
  onClose,
  onMock,
  timeline,
  scenario,
  onApply,
  onWhy,
}: {
  persona: Persona | null
  open: boolean
  onClose: () => void
  onMock: (message: string) => void
  /** The plan: the day the right arises, and the engine's point about the debt once it is in. */
  timeline?: Timeline | null
  scenario?: Scenario | null
  /** Put the certificate's amount into the plan (PATCH, with undo). */
  onApply?: PlanApply
  /** Open "Dlaczego tak?" on a point. */
  onWhy?: (focus: string) => void
}) {
  const [view, setView] = useState<View>('data')
  useEffect(() => {
    if (view !== 'issuing') return
    const timer = window.setTimeout(() => setView('certificate'), 900)
    return () => window.clearTimeout(timer)
  }, [view])
  const close = () => {
    onClose()
    window.setTimeout(() => setView('data'), 250)
  }

  return (
    <MockModal open={open && persona !== null} label="Twoje dane z ZUS" onClose={close} className="max-w-xl">
      {persona && (
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={view === 'certificate' ? 'certificate' : 'data'}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12, transition: { duration: 0.12 } }}
            transition={{ duration: 0.22, ease: EASE_OUT }}
            className="text-navy-700"
          >
            {view === 'certificate' ? (
              <DebtCertificate
                persona={persona}
                timeline={timeline ?? null}
                scenario={scenario ?? null}
                onApply={onApply}
                onWhy={onWhy}
                onBack={() => setView('data')}
              />
            ) : (
              <>
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
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <p className={cn('text-2xl font-bold tabular-nums', persona.debt === 0 ? 'text-zus-700' : 'text-alert-600')}>
                {formatPln(persona.debt)}
              </p>
              <p className="min-w-40 flex-1 text-sm text-navy-500">
                {persona.debt === 0
                  ? 'Brak zaległości w opłacaniu składek.'
                  : 'Liczy się zadłużenie w dniu powstania prawa do zasiłku.'}
              </p>
              <SmallButton onClick={() => setView('issuing')} disabled={view === 'issuing'}>
                {view === 'issuing' ? (
                  <>
                    <LoaderCircle className="size-4 animate-spin" /> Wystawiam…
                  </>
                ) : (
                  <>
                    <FileCheck2 className="size-4" /> Zaświadczenie
                  </>
                )}
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
              </>
            )}
          </motion.div>
        </AnimatePresence>
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

export function SmallButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-line px-3.5 text-sm font-bold text-navy-900 transition-[border-color,background-color,transform] duration-150 hover:border-navy-200 hover:bg-navy-50 active:scale-[0.97] disabled:opacity-70 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
    >
      {children}
    </button>
  )
}

/**
 * The simulated certificate: who it is for, the state on the day the right arises (or today, when
 * that day is still ahead) and the amount. Below it, what the debt means for the benefit: the
 * engine's own point once the amount is in the plan, never a rule written here.
 */
function DebtCertificate({
  persona,
  timeline,
  scenario,
  onApply,
  onWhy,
  onBack,
}: {
  persona: Persona
  timeline: Timeline | null
  scenario: Scenario | null
  onApply?: PlanApply
  onWhy?: (focus: string) => void
  onBack: () => void
}) {
  const parent: Role = scenario?.role === 'father' ? 'father' : 'mother'
  const right = timeline ? rightDay(timeline, parent) : null
  const today = timeline?.today ?? todayIso()
  const ahead = !right || right.date > today
  const none = persona.debt === 0
  const field = parent === 'mother' ? 'mother_contribution_debt' : 'father_contribution_debt'
  // The engine's point speaks of the plan's amount: shown only when it is this certificate's.
  const inPlan = scenario?.[field] === persona.debt
  const note = inPlan ? timeline?.notes.find((n) => n.id === `debt-${parent}`) : undefined
  // The engine's rule covers a parent who runs a business (engine/debt.py).
  const counts = scenario?.work === 'business' && !none && !inPlan
  const number = `SYM/${today.replaceAll('-', '')}/${persona.initials}`

  return (
    <div>
      <header className="flex items-start gap-3 pr-10">
        <Illustration src={ICONS.zaswiadczenie} size="event" className="bg-zus-50" />
        <div>
          <SimBadge>symulacja · dokument przykładowy</SimBadge>
          <h2 className="mt-2 text-2xl leading-tight font-bold tracking-tight text-navy-900">
            {none ? 'Zaświadczenie o niezaleganiu w opłacaniu składek' : 'Zaświadczenie o stanie zadłużenia z tytułu składek'}
          </h2>
        </div>
      </header>

      <div className="relative mt-5 overflow-hidden rounded-3xl border border-line bg-white px-5 py-4 shadow-[0_10px_30px_-20px_rgb(26_36_56/0.4)]">
        <p className="-mx-5 -mt-4 mb-3 bg-sun-100 px-5 py-1.5 text-center text-[11px] font-black tracking-wide text-sun-700 uppercase">
          Symulacja · dokument bez mocy prawnej
        </p>
        <dl className="divide-y divide-line text-sm">
          <CertRow label="Numer" value={number} />
          <CertRow label="Wystawiono" value={formatLongDate(today)} />
          <CertRow label="Dla" value={persona.name} />
          <CertRow label="Tytuł ubezpieczenia" value={persona.work} />
          <CertRow
            label="Stan na dzień"
            value={ahead ? `${formatLongDate(today)} (dziś)` : `${formatLongDate(right.date)} — powstanie prawa do zasiłku`}
          />
        </dl>
        <div className="mt-3 flex items-baseline justify-between gap-3 rounded-2xl bg-navy-50/70 px-4 py-3">
          <span className="text-sm text-navy-500">Zadłużenie z tytułu składek na ubezpieczenia społeczne</span>
          <span className={cn('shrink-0 text-xl font-black tabular-nums', none ? 'text-zus-700' : 'text-alert-600')}>
            {formatPln(persona.debt)}
          </span>
        </div>
      </div>

      {right && ahead && (
        <p className="mt-4 text-sm leading-relaxed text-navy-500">
          Prawo do zasiłku powstanie <b className="text-navy-900">{formatLongDate(right.date)}</b>
          {right.expected ? ' (według przewidywanej daty porodu)' : ''}. Liczy się zadłużenie w tym dniu.
        </p>
      )}

      {note ? (
        <div className={cn('mt-4 rounded-2xl px-4 py-3 text-sm leading-relaxed', note.kind === 'risk' ? 'bg-alert-50' : 'bg-zus-50')}>
          <p className="font-bold text-navy-900">{note.title}</p>
          <p className="mt-1 text-navy-700">
            <Emphasis text={note.text} className="text-navy-900" />
          </p>
          {onWhy && (
            <button
              type="button"
              onClick={() => onWhy(note.id)}
              className="mt-2 flex items-center gap-0.5 font-bold text-zus-700 underline-offset-4 hover:underline"
            >
              Podstawa prawna <ChevronRight className="size-4" />
            </button>
          )}
        </div>
      ) : (
        counts &&
        onApply && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <p className="min-w-48 flex-1 text-sm text-navy-500">Co ta kwota znaczy dla Waszego zasiłku, policzy plan.</p>
            <PrimaryButton
              onClick={() =>
                void onApply(
                  { [field]: persona.debt },
                  'Zadłużenie uwzględnione w planie',
                  'Co to znaczy dla zasiłku, mówi punkt pod zaświadczeniem.',
                )
              }
            >
              Uwzględnij w planie
            </PrimaryButton>
          </div>
        )
      )}

      <button
        type="button"
        onClick={onBack}
        className="mt-5 flex h-10 items-center gap-1.5 rounded-full px-3 text-sm font-bold text-navy-700 transition-colors hover:bg-navy-50"
      >
        <ArrowLeft className="size-4" /> Wróć do danych z ZUS
      </button>
    </div>
  )
}

function CertRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[8.5rem_1fr] gap-3 py-2">
      <dt className="text-navy-500">{label}</dt>
      <dd className="font-bold text-navy-900">{value}</dd>
    </div>
  )
}

/**
 * The day the parent's right to the maternity benefit arises, as the plan shows it: the first
 * day of the parent's first leave paid by it, else the birth (or the expected birth).
 */
function rightDay(timeline: Timeline, parent: Role): { date: string; expected: boolean } | null {
  const leave = timeline.segments
    .filter(
      (s) =>
        s.lane === parent &&
        s.tone !== 'work' &&
        /^(maternity|paternity|parental|supplementary)/.test(s.id),
    )
    .sort((a, b) => a.start.localeCompare(b.start))[0]
  const birth = timeline.markers.find((m) => m.id === 'birth' || m.id === 'due-date')
  const date = leave?.start ?? birth?.date
  if (!date) return null
  return { date, expected: birth?.id === 'due-date' }
}
