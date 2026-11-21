// Simulated login (FUNKCJE F30, brief: "należy wyłącznie zasymulować to logowanie"). It follows
// the steps of the real flow — choose a method on the national login node, scan the QR code in
// the mObywatel app, confirm the data the service asks for — but uses no official logos, asks for
// no password or PESEL, and says on every step that it is a simulation. Test accounts stand in
// for the phone (persona choice).
import { useEffect, useId, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, Building2, Check, ChevronRight, CreditCard, ShieldCheck } from 'lucide-react'
import { EASE_IN_OUT, EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { PERSONAS } from '@/lib/mockData'
import type { Persona } from '@/lib/mockData'
import { cn } from '@/lib/utils'
import { MockModal, SimBadge } from './MockModal'

type Step = 'method' | 'scan' | 'account' | 'consent'

const CODE_SECONDS = 5 * 60

export function MObywatelLogin({
  open,
  onClose,
  onLogin,
}: {
  open: boolean
  onClose: () => void
  onLogin: (persona: Persona) => void
}) {
  return (
    <MockModal open={open} label="Logowanie (symulacja)" onClose={onClose} className="max-w-[30rem]">
      <Flow onLogin={onLogin} />
    </MockModal>
  )
}

function Flow({ onLogin }: { onLogin: (persona: Persona) => void }) {
  const [step, setStep] = useState<Step>('method')
  const [persona, setPersona] = useState<Persona | null>(null)

  let screen: ReactNode
  switch (step) {
    case 'method':
      screen = <Method onMObywatel={() => setStep('scan')} />
      break
    case 'scan':
      screen = <Scan onConfirmed={() => setStep('account')} onBack={() => setStep('method')} />
      break
    case 'account':
      screen = (
        <Account
          onPick={(p) => {
            setPersona(p)
            setStep('consent')
          }}
        />
      )
      break
    case 'consent':
      screen = persona && (
        <Consent persona={persona} onAccept={() => onLogin(persona)} onBack={() => setStep('account')} />
      )
      break
  }

  return (
    <div>
      <div className="mb-5 flex items-center gap-2 pr-10">
        <ShieldCheck className="size-5 text-zus-600" />
        <p className="text-sm font-bold text-navy-900">Bezpieczne logowanie</p>
        <span className="ml-auto">
          <SimBadge>symulacja</SimBadge>
        </span>
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={step}
          initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.3, ease: EASE_OUT } }}
          exit={{ opacity: 0, filter: 'blur(4px)', transition: { duration: 0.15, ease: EASE_IN_OUT } }}
        >
          {screen}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

function Method({ onMObywatel }: { onMObywatel: () => void }) {
  return (
    <>
      <h2 className="text-2xl leading-tight font-bold tracking-tight text-navy-900">Wybierz sposób logowania</h2>
      <p className="mt-1.5 text-navy-500">Tak jak w krajowym węźle logowania. W symulacji działa aplikacja mObywatel.</p>
      <div className="mt-6 space-y-2">
        <Option
          icon={<img src={ICONS.telefon} alt="" draggable={false} className="size-9 object-contain" />}
          title="Aplikacja mObywatel"
          hint="Zeskanuj kod QR telefonem"
          recommended
          onClick={onMObywatel}
        />
        <Option icon={<ShieldCheck className="size-5" />} title="Profil zaufany" hint="Login i hasło lub bank" disabled />
        <Option icon={<CreditCard className="size-5" />} title="e-dowód" hint="Dowód osobisty z warstwą elektroniczną" disabled />
        <Option icon={<Building2 className="size-5" />} title="Bankowość elektroniczna" hint="Przez swój bank" disabled />
      </div>
    </>
  )
}

function Option({
  icon,
  title,
  hint,
  recommended,
  disabled,
  onClick,
}: {
  icon: ReactNode
  title: string
  hint: string
  recommended?: boolean
  disabled?: boolean
  onClick?: () => void
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={disabled}
      whileTap={disabled ? undefined : { scale: 0.98, transition: SPRING_PRESS }}
      className={cn(
        'group flex w-full items-center gap-4 rounded-2xl border px-4 py-3.5 text-left transition-[border-color,background-color] duration-200',
        'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        recommended ? 'border-zus-600 bg-zus-50 hover:bg-zus-100/70' : 'border-line',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <span
        className={cn(
          'grid size-10 shrink-0 place-items-center rounded-xl',
          recommended ? 'bg-white' : 'bg-navy-50 text-navy-500',
        )}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-bold text-navy-900">{title}</span>
        <span className="block text-sm text-navy-500">{hint}</span>
      </span>
      {disabled ? (
        <span className="text-xs font-bold text-navy-400">w symulacji niedostępne</span>
      ) : (
        <ChevronRight className="size-5 text-zus-700 transition-transform duration-150 group-hover:translate-x-0.5" />
      )}
    </motion.button>
  )
}

function Scan({ onConfirmed, onBack }: { onConfirmed: () => void; onBack: () => void }) {
  const [left, setLeft] = useState(CODE_SECONDS)
  const [confirming, setConfirming] = useState(false)
  const seed = useId()

  useEffect(() => {
    const id = window.setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000)
    return () => window.clearInterval(id)
  }, [])

  const confirm = () => {
    setConfirming(true)
    window.setTimeout(onConfirmed, 900)
  }

  return (
    <>
      <BackButton onClick={onBack} />
      <h2 className="text-2xl leading-tight font-bold tracking-tight text-navy-900">Zeskanuj kod w aplikacji</h2>
      <div className="mt-5 flex gap-5">
        <div className="relative shrink-0 rounded-3xl border border-line p-3">
          <QrCode seed={seed} />
          <AnimatePresence>
            {confirming && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="absolute inset-0 grid place-items-center rounded-3xl bg-white/85"
              >
                <motion.span
                  initial={{ scale: 0.6, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: 'spring', duration: 0.4, bounce: 0.3 }}
                  className="grid size-14 place-items-center rounded-full bg-zus-600 text-white"
                >
                  <Check className="size-7" strokeWidth={3} />
                </motion.span>
              </motion.span>
            )}
          </AnimatePresence>
        </div>
        <ol className="space-y-2.5 text-sm text-navy-700">
          {['Otwórz aplikację mObywatel w telefonie', 'Wybierz „Kod QR”', 'Zeskanuj kod i potwierdź logowanie'].map(
            (text, index) => (
              <li key={text} className="flex gap-2.5">
                <span className="grid size-5 shrink-0 place-items-center rounded-full bg-navy-50 text-[11px] font-black text-navy-700">
                  {index + 1}
                </span>
                {text}
              </li>
            ),
          )}
        </ol>
      </div>
      <p className="mt-4 text-sm text-navy-500">
        Kod wygaśnie za{' '}
        <span className="font-bold text-navy-900 tabular-nums">
          {Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}
        </span>
      </p>
      <PrimaryAction onClick={confirm} disabled={confirming}>
        {confirming ? 'Potwierdzono w telefonie' : 'Potwierdź w telefonie (symulacja)'}
      </PrimaryAction>
    </>
  )
}

function Account({ onPick }: { onPick: (persona: Persona) => void }) {
  return (
    <>
      <h2 className="text-2xl leading-tight font-bold tracking-tight text-navy-900">Wybierz konto testowe</h2>
      <p className="mt-1.5 text-navy-500">W prawdziwym logowaniu konto wynika z telefonu. Tu wybierasz przykładową osobę.</p>
      <div className="mt-5 space-y-2">
        {PERSONAS.map((p) => (
          <motion.button
            key={p.id}
            type="button"
            onClick={() => onPick(p)}
            whileTap={{ scale: 0.98, transition: SPRING_PRESS }}
            className="group flex w-full items-center gap-4 rounded-2xl border border-line px-4 py-3 text-left transition-[border-color,background-color] duration-200 hover:border-navy-200 hover:bg-navy-50/40 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
          >
            <Avatar initials={p.initials} />
            <span className="min-w-0 flex-1">
              <span className="block font-bold text-navy-900">{p.name}</span>
              <span className="block text-sm text-navy-500">{p.about}</span>
            </span>
            <ChevronRight className="size-5 text-navy-300 transition-transform duration-150 group-hover:translate-x-0.5" />
          </motion.button>
        ))}
      </div>
    </>
  )
}

function Consent({
  persona,
  onAccept,
  onBack,
}: {
  persona: Persona
  onAccept: () => void
  onBack: () => void
}) {
  const scopes = ['Imię i nazwisko', 'Numer PESEL', 'Dane o ubezpieczeniu z ZUS', 'Zaświadczenia lekarskie e-ZLA']
  return (
    <>
      <BackButton onClick={onBack} />
      <div className="flex items-center gap-3">
        <Avatar initials={persona.initials} />
        <div>
          <p className="font-bold text-navy-900">{persona.name}</p>
          <p className="text-sm text-navy-500">{persona.about}</p>
        </div>
      </div>
      <h2 className="mt-5 text-2xl leading-tight font-bold tracking-tight text-navy-900">
        Zasiłkowy Przewodnik prosi o dostęp do:
      </h2>
      <ul className="mt-4 space-y-2">
        {scopes.map((scope) => (
          <li key={scope} className="flex items-center gap-3 text-navy-700">
            <span className="grid size-5 place-items-center rounded-full bg-zus-100 text-zus-700">
              <Check className="size-3" strokeWidth={3} />
            </span>
            {scope}
          </li>
        ))}
      </ul>
      <p className="mt-4 text-sm text-navy-500">Dane są przykładowe. Nic nie jest wysyłane poza tę przeglądarkę.</p>
      <PrimaryAction onClick={onAccept}>Zgadzam się i loguję</PrimaryAction>
    </>
  )
}

function Avatar({ initials }: { initials: string }) {
  return (
    <span className="grid size-11 shrink-0 place-items-center rounded-full bg-navy-100 text-sm font-black text-navy-700">
      {initials}
    </span>
  )
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mb-3 -ml-2 flex items-center gap-1 rounded-full px-2 py-1 text-sm font-bold text-navy-500 transition-colors hover:text-navy-900"
    >
      <ArrowLeft className="size-4" /> Wstecz
    </button>
  )
}

function PrimaryAction({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={disabled}
      whileTap={disabled ? undefined : { scale: 0.97, transition: SPRING_PRESS }}
      className="mt-6 flex h-12 w-full items-center justify-center rounded-full bg-zus-600 font-bold text-white transition-[background-color,opacity] duration-200 hover:bg-zus-700 disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2 focus-visible:outline-none"
    >
      {children}
    </motion.button>
  )
}

const QR_SIZE = 25

/** Modules of a QR-like pattern (not a real code), seeded so it stays the same per screen. */
function qrCells(seed: string): [number, number][] {
  let state = [...seed].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7)
  const random = () => {
    state = (state * 1664525 + 1013904223) >>> 0
    return state / 2 ** 32
  }
  const finder = (x: number, y: number) =>
    (x < 8 && y < 8) || (x >= QR_SIZE - 8 && y < 8) || (x < 8 && y >= QR_SIZE - 8)
  const out: [number, number][] = []
  for (let y = 0; y < QR_SIZE; y += 1) {
    for (let x = 0; x < QR_SIZE; x += 1) {
      if (!finder(x, y) && random() > 0.52) out.push([x, y])
    }
  }
  return out
}

/** A QR-like pattern: three finder squares and the seeded modules. */
function QrCode({ seed }: { seed: string }) {
  const cells = useMemo(() => qrCells(seed), [seed])
  const finders = [
    [0, 0],
    [QR_SIZE - 7, 0],
    [0, QR_SIZE - 7],
  ]
  return (
    <svg viewBox={`0 0 ${QR_SIZE} ${QR_SIZE}`} className="size-36 text-navy-900" aria-label="Kod QR (symulacja)">
      {cells.map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill="currentColor" />
      ))}
      {finders.map(([x, y]) => (
        <g key={`${x}-${y}`} fill="currentColor">
          <path d={`M${x} ${y}h7v7h-7z M${x + 1} ${y + 1}v5h5v-5z`} fillRule="evenodd" />
          <rect x={x + 2} y={y + 2} width={3} height={3} />
        </g>
      ))}
    </svg>
  )
}
