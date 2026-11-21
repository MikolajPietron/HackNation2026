import { useCallback, useState } from 'react'
import type { ReactNode } from 'react'
import { ChatPanel } from './components/chat/ChatPanel'
import { CalendarIcon, ChatIcon, HeartIcon } from './components/Icons'
import { TimelinePanel } from './components/timeline/TimelinePanel'
import { useAssistant } from './hooks/useAssistant'
import { cx } from './lib/ui'

type Tab = 'chat' | 'timeline'

export default function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const [unseen, setUnseen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focus, setFocus] = useState<{ id: string | null; tick: number }>({ id: null, tick: 0 })

  const focusOn = useCallback((id: string) => {
    setSelectedId(id)
    setFocus((f) => ({ id, tick: f.tick + 1 }))
  }, [])
  const markUnseen = useCallback(() => setUnseen(true), [])
  const { messages, busy, send, timeline, changed } = useAssistant({
    onFocus: focusOn,
    onTimeline: markUnseen,
  })

  // Phones show one panel at a time; from `lg` both are side by side and the tabs are hidden.
  const openTab = (next: Tab) => {
    setTab(next)
    setUnseen(false)
    if (next === 'timeline') setFocus((f) => ({ id: selectedId, tick: f.tick + 1 }))
  }
  const showTimeline = (elementId: string | null) => {
    openTab('timeline')
    if (elementId) focusOn(elementId)
  }

  return (
    <div className="flex h-dvh flex-col bg-stone-50 text-stone-900">
      <header className="flex items-center justify-between gap-3 border-b border-stone-200 bg-white px-4 py-3 lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-rose-500 text-white">
            <HeartIcon className="size-5" />
          </span>
          <div className="min-w-0 leading-tight">
            <h1 className="truncate text-[15px] font-semibold sm:text-base">
              Zasiłkowy Przewodnik Przyszłego Rodzica
            </h1>
            <p className="hidden text-xs text-stone-500 sm:block">
              Urlopy i zasiłki po narodzinach dziecka — według Przewodnika ZUS
            </p>
          </div>
        </div>
        <span className="hidden shrink-0 rounded-full bg-stone-100 px-3 py-1 text-xs font-medium text-stone-600 md:inline">
          Wersja demonstracyjna
        </span>
      </header>

      <nav className="grid grid-cols-2 gap-1 border-b border-stone-200 bg-white p-1.5 lg:hidden" aria-label="Widok">
        <TabButton active={tab === 'chat'} onClick={() => openTab('chat')} icon={<ChatIcon />}>
          Rozmowa
        </TabButton>
        <TabButton
          active={tab === 'timeline'}
          onClick={() => openTab('timeline')}
          icon={<CalendarIcon />}
          badge={unseen && tab === 'chat'}
        >
          Oś czasu
        </TabButton>
      </nav>

      <main className="flex min-h-0 flex-1">
        <section
          className={cx('min-h-0 flex-1 overflow-y-auto', tab !== 'timeline' && 'hidden lg:block')}
          aria-label="Oś czasu"
        >
          <TimelinePanel
            timeline={timeline}
            changed={changed}
            selectedId={selectedId}
            focus={focus}
            onSelect={setSelectedId}
          />
        </section>
        <aside
          className={cx(
            'min-h-0 w-full flex-col bg-white lg:flex lg:w-[400px] lg:shrink-0 lg:border-l lg:border-stone-200',
            tab === 'chat' ? 'flex' : 'hidden',
          )}
          aria-label="Rozmowa z asystentem"
        >
          <ChatPanel messages={messages} busy={busy} onSend={send} onShowTimeline={showTimeline} />
        </aside>
      </main>
    </div>
  )
}

function TabButton({
  active,
  onClick,
  icon,
  badge = false,
  children,
}: {
  active: boolean
  onClick: () => void
  icon: ReactNode
  badge?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cx(
        'relative flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition',
        active ? 'bg-stone-900 text-white' : 'text-stone-600 hover:bg-stone-100',
      )}
    >
      {icon}
      {children}
      {badge && (
        <span className="absolute top-1.5 right-3 size-2 rounded-full bg-rose-500" aria-label="nowe zmiany" />
      )}
    </button>
  )
}
