// "Wniosek o odpis aktu urodzenia" (FUNKCJE F35, a simulation the brief asks for). The requests on
// the timeline need a short copy of the birth certificate as an attachment (the regulations'
// forms), so the plan offers to order one. Nothing is sent and no personal data is asked for:
// the flow shows the choices a real service would ask about and ends with a clear "symulacja".
import { useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, Check } from 'lucide-react'
import { MockModal, SimBadge } from '@/components/mocks/MockModal'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import { Illustration } from '@/components/ui/illustration'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { cn } from '@/lib/utils'

type Kind = 'short' | 'full' | 'multilingual'
type Delivery = 'online' | 'post' | 'office'

const KINDS: { id: Kind; title: string; hint: string }[] = [
  { id: 'short', title: 'Odpis skrócony', hint: 'Ten jest załącznikiem do wniosków na Waszej osi' },
  { id: 'full', title: 'Odpis zupełny', hint: 'Pełna treść aktu z wpisami' },
  { id: 'multilingual', title: 'Odpis wielojęzyczny', hint: 'Do użycia za granicą' },
]
const DELIVERY: { id: Delivery; title: string; icon: string }[] = [
  { id: 'online', title: 'Elektronicznie, na konto', icon: ICONS.telefon },
  { id: 'post', title: 'Pocztą', icon: ICONS.koperta },
  { id: 'office', title: 'Osobiście w urzędzie', icon: ICONS.dom },
]

type Step = 'kind' | 'delivery' | 'confirm' | 'done'

export function BirthCertificate({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [step, setStep] = useState<Step>('kind')
  const [kind, setKind] = useState<Kind>('short')
  const [delivery, setDelivery] = useState<Delivery>('online')
  const close = () => {
    onClose()
    window.setTimeout(() => setStep('kind'), 250)
  }
  const back: Partial<Record<Step, Step>> = { delivery: 'kind', confirm: 'delivery' }

  return (
    <MockModal open={open} label="Odpis aktu urodzenia" onClose={close} className="max-w-xl">
      <header className="flex items-start gap-3 pr-10">
        <Illustration src={ICONS.aktUrodzenia} size="event" className="bg-zus-50" />
        <div>
          <SimBadge>symulacja · nic nie jest wysyłane</SimBadge>
          <h2 className="mt-2 text-2xl leading-tight font-bold tracking-tight text-navy-900">Odpis aktu urodzenia</h2>
        </div>
      </header>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12, transition: { duration: 0.12 } }}
          transition={{ duration: 0.22, ease: EASE_OUT }}
          className="mt-5"
        >
          {step === 'kind' && (
            <Question title="Jaki odpis?">
              {KINDS.map((k) => (
                <Option key={k.id} selected={kind === k.id} onClick={() => setKind(k.id)} title={k.title} hint={k.hint} />
              ))}
              <Next onClick={() => setStep('delivery')} />
            </Question>
          )}
          {step === 'delivery' && (
            <Question title="Jak chcesz go odebrać?">
              {DELIVERY.map((d) => (
                <Option key={d.id} selected={delivery === d.id} onClick={() => setDelivery(d.id)} title={d.title} icon={d.icon} />
              ))}
              <Next onClick={() => setStep('confirm')} />
            </Question>
          )}
          {step === 'confirm' && (
            <Question title="Sprawdź i złóż">
              <dl className="divide-y divide-line rounded-2xl border border-line text-sm">
                <Row label="Odpis" value={KINDS.find((k) => k.id === kind)!.title} />
                <Row label="Odbiór" value={DELIVERY.find((d) => d.id === delivery)!.title} />
                <Row label="Dane dziecka i rodzica" value="z konta, po zalogowaniu (w symulacji ich nie podajesz)" />
              </dl>
              <PrimaryButton onClick={() => setStep('done')} className="mt-4 h-12 w-full text-base">
                Złóż wniosek (symulacja)
              </PrimaryButton>
            </Question>
          )}
          {step === 'done' && (
            <div className="flex flex-col items-center py-4 text-center">
              <motion.span
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 380, damping: 22 }}
                className="grid size-16 place-items-center rounded-full bg-zus-600 text-white"
              >
                <Check className="size-8" strokeWidth={3} />
              </motion.span>
              <p className="mt-4 text-xl font-bold text-navy-900">Wniosek złożony</p>
              <p className="mt-1 max-w-sm text-sm text-pretty text-navy-500">
                To symulacja: nic nie zostało wysłane. Gdy będziesz mieć odpis, zaznacz go w załącznikach wniosku.
              </p>
              <button
                type="button"
                onClick={close}
                className="mt-5 h-11 rounded-full border border-line px-5 font-bold text-navy-700 transition-colors hover:bg-navy-50"
              >
                Wróć do planu
              </button>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {back[step] && (
        <button
          type="button"
          onClick={() => setStep(back[step]!)}
          className="mt-3 flex items-center gap-1.5 text-sm font-bold text-navy-500 hover:text-navy-900"
        >
          <ArrowLeft className="size-4" /> Wstecz
        </button>
      )}
    </MockModal>
  )
}

function Question({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div role="radiogroup" aria-label={title}>
      <p className="mb-3 font-bold text-navy-900">{title}</p>
      <div className="space-y-2">{children}</div>
    </div>
  )
}

function Option({
  selected,
  onClick,
  title,
  hint,
  icon,
}: {
  selected: boolean
  onClick: () => void
  title: string
  hint?: string
  icon?: string
}) {
  return (
    <motion.button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      whileTap={{ scale: 0.98, transition: SPRING_PRESS }}
      className={cn(
        'flex w-full items-center gap-3 rounded-2xl border px-4 py-3 text-left transition-[border-color,background-color] duration-150',
        'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        selected ? 'border-zus-600 bg-zus-50 shadow-[0_0_0_1px_var(--color-zus-600)]' : 'border-line hover:border-navy-200',
      )}
    >
      {icon && <Illustration src={icon} size="hint" />}
      <span className="min-w-0 flex-1">
        <span className="block font-bold text-navy-900">{title}</span>
        {hint && <span className="block text-sm text-navy-500">{hint}</span>}
      </span>
      <span
        className={cn(
          'grid size-5 shrink-0 place-items-center rounded-full border-2',
          selected ? 'border-zus-600 bg-zus-600 text-white' : 'border-navy-200',
        )}
      >
        {selected && <Check className="size-3" strokeWidth={3.5} />}
      </span>
    </motion.button>
  )
}

function Next({ onClick }: { onClick: () => void }) {
  return (
    <PrimaryButton onClick={onClick} className="mt-2 h-12 w-full text-base">
      Dalej
    </PrimaryButton>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 px-4 py-2.5 sm:flex-row sm:justify-between sm:gap-4">
      <dt className="text-navy-500">{label}</dt>
      <dd className="font-bold text-navy-900 sm:text-right">{value}</dd>
    </div>
  )
}
