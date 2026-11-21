// The top bar across the whole app: our mark, then the services a ZUS customer expects —
// contact, language, accessibility, search, PUE/eZUS. Most of them are mocks for now (FUNKCJE:
// simulations are clearly marked), reported through `onMock`. "Większy tekst" already works;
// "Czytaj na głos" is the place for the ElevenLabs voice (F40).
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
  Ear,
  FolderOpen,
  LogOut,
  Search,
  UserRound,
  Type,
  Volume2,
} from 'lucide-react'
import { useLargeText } from '@/hooks/useLargeText'
import { EASE_OUT } from '@/lib/ease'
import type { Persona } from '@/lib/mockData'
import { cn } from '@/lib/utils'
import { Brand } from './Brand'

interface TopBarProps {
  onMock: (message: string) => void
  /** Simulated login (mObywatel) and what it unlocks. */
  persona: Persona | null
  onLogin: () => void
  onLogout: () => void
  onZusData: () => void
  /** Example cases for the jury. */
  onCases: () => void
  className?: string
}

export function TopBar({ onMock, persona, onLogin, onLogout, onZusData, onCases, className }: TopBarProps) {
  return (
    <header
      className={cn(
        'flex h-[72px] shrink-0 items-center gap-2 border-b border-line bg-white px-6',
        className,
      )}
    >
      <Brand />
      <nav aria-label="Usługi" className="ml-auto flex items-center gap-1">
        <TextButton onClick={onCases} className="flex gap-1.5">
          <FolderOpen className="size-4" /> Przykładowe sprawy
        </TextButton>
        <TextButton
          className="hidden 2xl:flex"
          onClick={() => onMock('Kontakt i pomoc pojawią się w wersji demo.')}
        >
          Kontakt
        </TextButton>
        <LanguageMenu onMock={onMock} />
        <Divider />
        <IconButton
          label="Tłumacz języka migowego"
          onClick={() => onMock('Wideotłumacz polskiego języka migowego jest w przygotowaniu.')}
        >
          <Ear className="size-5" />
        </IconButton>
        <AccessibilityMenu onMock={onMock} />
        <Divider />
        <IconButton label="Szukaj" onClick={() => onMock('Wyszukiwanie w Przewodniku ZUS — wkrótce.')}>
          <Search className="size-5" />
        </IconButton>
        {persona ? (
          <AccountMenu persona={persona} onZusData={onZusData} onLogout={onLogout} />
        ) : (
          <>
            <button
              type="button"
              onClick={() => onMock('Rejestracja w PUE/eZUS to atrapa integracji.')}
              className="ml-2 flex h-10 items-center rounded-full border border-navy-200 px-4 text-sm font-bold whitespace-nowrap text-navy-900 transition-[border-color,background-color,transform] duration-150 hover:border-navy-400 hover:bg-navy-50 active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
            >
              <span>
                Zarejestruj<span className="hidden 2xl:inline"> w PUE/eZUS</span>
              </span>
            </button>
            <button
              type="button"
              onClick={onLogin}
              className="group flex h-10 items-center gap-1 rounded-full bg-sun-400 pr-3 pl-4 text-sm font-bold whitespace-nowrap text-navy-900 transition-[background-color,transform] duration-150 hover:bg-sun-300 active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2 focus-visible:outline-none"
            >
              <span>
                Zaloguj<span className="hidden xl:inline"> do PUE/eZUS</span>
              </span>
              <ChevronRight className="size-4 transition-transform duration-150 group-hover:translate-x-0.5" />
            </button>
          </>
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

function LanguageMenu({ onMock }: { onMock: (message: string) => void }) {
  return (
    <Menu
      label="Język"
      trigger={
        <span className="flex items-center gap-1 px-1 text-sm font-bold">
          PL
          <ChevronDown className="size-4 text-navy-400" />
        </span>
      }
    >
      {(close) => (
        <>
          <MenuItem icon={<span className="text-xs font-black">PL</span>} checked onClick={close}>
            Polski
          </MenuItem>
          <MenuItem
            icon={<span className="text-xs font-black">EN</span>}
            soon
            onClick={() => {
              close()
              onMock('Wersja angielska — wkrótce.')
            }}
          >
            English
          </MenuItem>
          <MenuItem
            icon={<span className="text-xs font-black">UA</span>}
            soon
            onClick={() => {
              close()
              onMock('Wersja ukraińska — wkrótce.')
            }}
          >
            Українська
          </MenuItem>
        </>
      )}
    </Menu>
  )
}

function AccessibilityMenu({ onMock }: { onMock: (message: string) => void }) {
  const [largeText, setLargeText] = useLargeText()

  return (
    <Menu label="Dostępność" trigger={<Accessibility className="size-5" />} icon>
      {(close) => (
        <>
          <MenuItem
            icon={<Volume2 className="size-4" />}
            soon
            onClick={() => {
              close()
              onMock('Czytanie na głos przygotowujemy z ElevenLabs.')
            }}
          >
            Czytaj na głos
          </MenuItem>
          <MenuItem
            icon={<Type className="size-4" />}
            checked={largeText}
            onClick={() => setLargeText(!largeText)}
          >
            Większy tekst
          </MenuItem>
          <MenuItem
            icon={<Contrast className="size-4" />}
            soon
            onClick={() => {
              close()
              onMock('Tryb wysokiego kontrastu — wkrótce.')
            }}
          >
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
  soon = false,
  onClick,
  children,
}: {
  icon: ReactNode
  checked?: boolean
  soon?: boolean
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
      {soon && (
        <span className="rounded-full bg-navy-50 px-2 py-0.5 text-[11px] font-bold text-navy-500">wkrótce</span>
      )}
      {checked && <Check className="size-4 text-zus-600" strokeWidth={3} />}
    </button>
  )
}

function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="grid size-10 place-items-center rounded-full text-navy-700 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.95] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
    >
      {children}
    </button>
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
        'h-10 items-center rounded-full px-3 text-sm font-bold text-navy-700 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
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
