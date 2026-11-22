// The top bar across the whole app: our mark, then only what works — the letter from ZUS, the
// example cases, the parameters panel, accessibility (larger text, contrast, reading aloud with
// the device's own Polish voice) and the simulated PUE/eZUS login through mObywatel (the brief
// asks for the simulation). Mocks with nothing behind them (contact, languages, sign language,
// search, registration) were removed on 22.11.2026.
//
// Menus follow Emil Kowalski's rules: they grow from their trigger (origin-aware), from scale 0.96
// with opacity, ease-out in ~160 ms, and close faster than they open.
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  Accessibility,
  Check,
  ChevronDown,
  ChevronRight,
  Contrast,
  FolderOpen,
  LogOut,
  Mail,
  Settings2,
  Square,
  UserRound,
  Type,
  Volume2,
} from 'lucide-react'
import { useHighContrast } from '@/hooks/useHighContrast'
import { useLargeText } from '@/hooks/useLargeText'
import { EASE_OUT } from '@/lib/ease'
import { canReadAloud, readAloud, stopReading, useReading } from '@/lib/speech'
import type { Persona } from '@/lib/mockData'
import { cn } from '@/lib/utils'
import { Brand } from './Brand'

interface TopBarProps {
  /** Simulated login (mObywatel) and what it unlocks. */
  persona: Persona | null
  onLogin: () => void
  onLogout: () => void
  onZusData: () => void
  /** Example cases for the jury. */
  onCases: () => void
  /** "Przetłumacz pismo z ZUS" (AI). */
  onLetter: () => void
  /** The logo leads back to the start screen. */
  onHome?: () => void
  className?: string
}

export function TopBar({ persona, onLogin, onLogout, onZusData, onCases, onLetter, onHome, className }: TopBarProps) {
  return (
    <header
      className={cn(
        'flex h-[72px] shrink-0 items-center gap-2 border-b border-line bg-white px-6',
        className,
      )}
    >
      {onHome ? (
        <button
          type="button"
          onClick={onHome}
          title="Ekran startowy"
          className="-ml-2 rounded-2xl px-2 py-1 transition-colors hover:bg-navy-50 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
        >
          <Brand />
        </button>
      ) : (
        <Brand />
      )}
      <nav aria-label="Usługi" className="ml-auto flex items-center gap-1">
        <TextButton onClick={onLetter} className="flex gap-1.5">
          <Mail className="size-4" /> <Label short="Pismo">Pismo z ZUS</Label>
        </TextButton>
        <TextButton onClick={onCases} className="flex gap-1.5">
          <FolderOpen className="size-4" /> <Label short="Sprawy">Przykładowe sprawy</Label>
        </TextButton>
        {/* The parameters panel (the brief requires it): numbers of the law in versions by date. */}
        <a
          href="/admin"
          className="flex h-10 items-center gap-1.5 rounded-full px-3 text-sm font-bold whitespace-nowrap text-navy-700 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
        >
          <Settings2 className="size-4" /> <Label short="Admin">Panel admina</Label>
        </a>
        <Divider />
        <AccessibilityMenu />
        {persona ? (
          <AccountMenu persona={persona} onZusData={onZusData} onLogout={onLogout} />
        ) : (
          <button
            type="button"
            onClick={onLogin}
            className="group ml-2 flex h-10 items-center gap-1 rounded-full bg-sun-400 pr-3 pl-4 text-sm font-bold whitespace-nowrap text-navy-900 transition-[background-color,transform] duration-150 hover:bg-sun-300 active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2 focus-visible:outline-none"
          >
            <span>
              Zaloguj<span className="hidden xl:inline"> do PUE/eZUS</span>
            </span>
            <ChevronRight className="size-4 transition-transform duration-150 group-hover:translate-x-0.5" />
          </button>
        )}
      </nav>
    </header>
  )
}

function AccountMenu({
  persona,
  onZusData,
  onLogout,
}: {
  persona: Persona
  onZusData: () => void
  onLogout: () => void
}) {
  return (
    <Menu
      label="Konto"
      trigger={
        <span className="flex items-center gap-2 pr-1 text-sm font-bold">
          <span className="grid size-7 place-items-center rounded-full bg-navy-100 text-[11px] font-black text-navy-700">
            {persona.initials}
          </span>
          {persona.name.split(' ')[0]}
          <span className="rounded-full bg-sun-100 px-1.5 py-0.5 text-[10px] font-bold text-sun-700">symulacja</span>
          <ChevronDown className="size-4 text-navy-400" />
        </span>
      }
    >
      {(close) => (
        <>
          <MenuItem
            icon={<UserRound className="size-4" />}
            onClick={() => {
              close()
              onZusData()
            }}
          >
            Moje dane z ZUS
          </MenuItem>
          <MenuItem
            icon={<LogOut className="size-4" />}
            onClick={() => {
              close()
              onLogout()
            }}
          >
            Wyloguj
          </MenuItem>
        </>
      )}
    </Menu>
  )
}

function AccessibilityMenu() {
  const [largeText, setLargeText] = useLargeText()
  const [contrast, setContrast] = useHighContrast()
  const reading = useReading()

  return (
    <Menu label="Dostępność" trigger={<Accessibility className="size-5" />} icon>
      {(close) => (
        <>
          {(reading || canReadAloud()) && (
            <MenuItem
              icon={reading ? <Square className="size-4" /> : <Volume2 className="size-4" />}
              onClick={() => {
                close()
                if (reading) stopReading()
                else readAloud()
              }}
            >
              {reading ? 'Zatrzymaj czytanie' : 'Czytaj na głos'}
            </MenuItem>
          )}
          <MenuItem
            icon={<Type className="size-4" />}
            checked={largeText}
            onClick={() => setLargeText(!largeText)}
          >
            Większy tekst
          </MenuItem>
          <MenuItem icon={<Contrast className="size-4" />} checked={contrast} onClick={() => setContrast(!contrast)}>
            Wysoki kontrast
          </MenuItem>
        </>
      )}
    </Menu>
  )
}

/** A trigger with a small menu that grows from it. Closes on outside click and Escape. */
function Menu({
  label,
  trigger,
  icon = false,
  children,
}: {
  label: string
  trigger: ReactNode
  icon?: boolean
  children: (close: () => void) => ReactNode
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('pointerdown', onDown)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-label={label}
        title={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'grid h-10 place-items-center rounded-full text-navy-700 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.95] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
          icon ? 'w-10' : 'px-3',
          open && 'bg-navy-50 text-navy-900',
        )}
      >
        {trigger}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            aria-label={label}
            initial={{ opacity: 0, scale: 0.96, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.1 } }}
            transition={{ duration: 0.16, ease: EASE_OUT }}
            style={{ transformOrigin: 'top right' }}
            className="absolute top-full right-0 z-50 mt-2 w-64 rounded-3xl border border-line bg-white p-1.5 shadow-[0_18px_40px_-20px_rgb(26_36_56/0.3)]"
          >
            {children(() => setOpen(false))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function MenuItem({
  icon,
  checked = false,
  onClick,
  children,
}: {
  icon: ReactNode
  checked?: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left text-sm font-bold text-navy-900 transition-[background-color,transform] duration-150 hover:bg-navy-50 active:scale-[0.98] focus-visible:bg-navy-50 focus-visible:outline-none"
    >
      <span className="grid size-6 place-items-center text-navy-500">{icon}</span>
      <span className="flex-1">{children}</span>
      {checked && <Check className="size-4 text-zus-600" strokeWidth={3} />}
    </button>
  )
}

/** A label that is shorter on a narrow laptop (below 1280 px); the full words for screen readers. */
function Label({ short, children }: { short: string; children: string }) {
  return (
    <>
      <span className="hidden xl:inline">{children}</span>
      <span className="xl:hidden" aria-hidden>
        {short}
      </span>
      <span className="sr-only xl:hidden">{children}</span>
    </>
  )
}

function TextButton({
  onClick,
  className,
  children,
}: {
  onClick: () => void
  className?: string
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'h-10 items-center rounded-full px-3 text-sm font-bold whitespace-nowrap text-navy-700 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        className,
      )}
    >
      {children}
    </button>
  )
}

function Divider() {
  return <span aria-hidden className="mx-1 h-6 w-px bg-line" />
}
