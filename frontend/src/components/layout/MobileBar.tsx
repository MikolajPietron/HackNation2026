// The top bar on phones: our mark, sign-in and one menu. The menu is a sheet from the bottom
// (Vaul, via components/ui/sheet) with everything the wide top bar has: example cases, language,
// accessibility, the ZUS services, how we count, start over and the admin panel. Only what works
// (mocks with nothing behind them were removed on 22.11.2026, as in the wide top bar).
import { useState } from 'react'
import type { ReactNode } from 'react'
import {
  Calculator,
  Check,
  Contrast,
  FolderOpen,
  HeartHandshake,
  LogOut,
  Mail,
  Menu,
  RotateCcw,
  Settings2,
  Share2,
  Square,
  Type,
  UserRound,
  Volume2,
} from 'lucide-react'
import { Sheet } from '@/components/ui/sheet'
import { useHighContrast } from '@/hooks/useHighContrast'
import { useLargeText } from '@/hooks/useLargeText'
import { canReadAloud, readAloud, stopReading, useReading } from '@/lib/speech'
import type { Persona } from '@/lib/mockData'
import { cn } from '@/lib/utils'
import { BrandMark } from './Brand'

interface Props {
  persona: Persona | null
  onLogin: () => void
  onLogout: () => void
  onZusData: () => void
  onCases: () => void
  onLetter: () => void
  onAbout: () => void
  onSupport: () => void
  onStartOver: () => void
  /** "Udostępnij plan": a read-only link for the partner. */
  onShare?: () => void
}

export function MobileBar(props: Props) {
  const { persona, onLogin, onZusData } = props
  const [menu, setMenu] = useState(false)
  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line bg-white pr-2 pl-4">
      <BrandMark size="sm" />
      <p className="min-w-0 flex-1 text-[13px] leading-tight font-bold">
        <span className="block text-navy-900">Zasiłkowy Przewodnik</span>
        <span className="block text-zus-700">Przyszłego Rodzica</span>
      </p>
      {persona ? (
        <button
          type="button"
          onClick={onZusData}
          aria-label="Moje dane z ZUS"
          className="grid size-10 place-items-center rounded-full bg-navy-100 text-xs font-black text-navy-700 transition-transform duration-150 active:scale-[0.94]"
        >
          {persona.initials}
        </button>
      ) : (
        <button
          type="button"
          onClick={onLogin}
          className="h-9 rounded-full bg-sun-400 px-3.5 text-sm font-bold text-navy-900 transition-[background-color,transform] duration-150 active:scale-[0.96]"
        >
          Zaloguj
        </button>
      )}
      <button
        type="button"
        onClick={() => setMenu(true)}
        aria-label="Menu"
        className="grid size-10 place-items-center rounded-full text-navy-700 transition-[background-color,transform] duration-150 active:scale-[0.94] active:bg-navy-50"
      >
        <Menu className="size-5" />
      </button>
      <Sheet open={menu} onOpenChange={setMenu} title="Menu">
        <MenuContent {...props} close={() => setMenu(false)} />
      </Sheet>
    </header>
  )
}

function MenuContent({
  persona,
  onLogin,
  onLogout,
  onZusData,
  onCases,
  onLetter,
  onAbout,
  onSupport,
  onStartOver,
  onShare,
  close,
}: Props & { close: () => void }) {
  const [largeText, setLargeText] = useLargeText()
  const [contrast, setContrast] = useHighContrast()
  const reading = useReading()
  const then = (action: () => void) => () => {
    close()
    action()
  }
  return (
    <nav aria-label="Menu" className="space-y-5">
      <Group>
        {onShare && (
          <Item icon={<Share2 />} onClick={then(onShare)}>
            Udostępnij plan partnerowi
          </Item>
        )}
        <Item icon={<Mail />} onClick={then(onLetter)} meta="AI">
          Przetłumacz pismo z ZUS
        </Item>
        <Item icon={<FolderOpen />} onClick={then(onCases)}>
          Przykładowe sprawy
        </Item>
        <Item icon={<Calculator />} onClick={then(onAbout)}>
          Jak to liczymy?
        </Item>
        <Item icon={<HeartHandshake />} onClick={then(onSupport)}>
          Wsparcie dla rodziców
        </Item>
        <Item icon={<RotateCcw />} onClick={then(onStartOver)}>
          Zacznij od nowa
        </Item>
      </Group>

      <Group title="Konto">
        {persona ? (
          <>
            <Item icon={<UserRound />} onClick={then(onZusData)} meta={persona.name}>
              Moje dane z ZUS
            </Item>
            <Item icon={<LogOut />} onClick={then(onLogout)}>
              Wyloguj
            </Item>
          </>
        ) : (
          <Item icon={<UserRound />} onClick={then(onLogin)} meta="mObywatel · symulacja">
            Zaloguj do PUE/eZUS
          </Item>
        )}
      </Group>

      <Group title="Dostępność">
        <Item icon={<Type />} onClick={() => setLargeText(!largeText)} checked={largeText}>
          Większy tekst
        </Item>
        {(reading || canReadAloud()) && (
          <Item
            icon={reading ? <Square /> : <Volume2 />}
            meta="Zaznaczony tekst albo Twoja sytuacja"
            onClick={then(reading ? stopReading : readAloud)}
          >
            {reading ? 'Zatrzymaj czytanie' : 'Czytaj na głos'}
          </Item>
        )}
        <Item icon={<Contrast />} onClick={() => setContrast(!contrast)} checked={contrast}>
          Wysoki kontrast
        </Item>
      </Group>

      <Group title="Więcej">
        <Item icon={<Settings2 />} href="/admin" meta="demo">
          Panel administracyjny
        </Item>
      </Group>
    </nav>
  )
}

function Group({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section>
      {title && <h3 className="mb-1 px-3 text-xs font-bold text-navy-400">{title}</h3>}
      <div className="divide-y divide-line rounded-2xl border border-line">{children}</div>
    </section>
  )
}

function Item({
  icon,
  meta,
  checked,
  href,
  onClick,
  children,
}: {
  icon: ReactNode
  meta?: string
  checked?: boolean
  href?: string
  onClick?: () => void
  children: ReactNode
}) {
  const content = (
    <>
      <span className="grid size-8 shrink-0 place-items-center text-navy-500 [&_svg]:size-5">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-bold text-navy-900">{children}</span>
        {meta && <span className="block text-sm text-navy-500">{meta}</span>}
      </span>
      {checked !== undefined && (
        <span
          className={cn(
            'grid size-6 place-items-center rounded-full border-2 transition-colors duration-150',
            checked ? 'border-zus-600 bg-zus-600 text-white' : 'border-navy-200',
          )}
        >
          {checked && <Check className="size-3.5" strokeWidth={3} />}
        </span>
      )}
    </>
  )
  const className =
    'flex w-full items-center gap-3 px-3 py-3 text-left transition-[background-color] duration-150 active:bg-navy-50 first:rounded-t-2xl last:rounded-b-2xl'
  return href ? (
    <a href={href} className={className}>
      {content}
    </a>
  ) : (
    <button type="button" onClick={onClick} className={className}>
      {content}
    </button>
  )
}
