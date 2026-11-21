import { useCallback, useState } from 'react'
import { motion, MotionConfig } from 'motion/react'
import { RotateCcw } from 'lucide-react'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { AboutPanel } from '@/components/layout/AboutPanel'
import { BottomNav, Logo, Rail } from '@/components/layout/Navigation'
import type { Tab } from '@/components/layout/Navigation'
import { ApplicationsList, SummaryTiles } from '@/components/summary/Summary'
import { TimelinePanel } from '@/components/timeline/TimelinePanel'
import { useAssistant } from '@/hooks/useAssistant'
import { EASE_OUT } from '@/lib/ease'
import { cn } from '@/lib/utils'

const APP_NAME = 'Zasiłkowy Przewodnik Przyszłego Rodzica'

export default function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const [unseen, setUnseen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focus, setFocus] = useState<{ id: string | null; tick: number }>({ id: null, tick: 0 })

  const focusOn = useCallback((id: string) => {
    setSelectedId(id)
    setFocus((f) => ({ id, tick: f.tick + 1 }))
  }, [])
  // A recalculated timeline scrolls to what changed but opens nothing: details are on demand.
  const timelineChanged = useCallback((focusId: string | null) => {
    setUnseen(true)
    if (focusId) setFocus((f) => ({ id: focusId, tick: f.tick + 1 }))
  }, [])
  const { messages, busy, send, stop, reset, timeline, changed } = useAssistant({
    onFocus: focusOn,
    onTimeline: timelineChanged,
  })

  // Phones show one panel at a time. From `lg` the chat is always on the right and the
  // tab only switches the middle between the timeline and the assumptions.
  const openTab = (next: Tab) => {
    setTab(next)
    setUnseen(false)
    if (next === 'timeline') setFocus((f) => ({ id: selectedId, tick: f.tick + 1 }))
  }
  const showOnTimeline = (elementId: string | null) => {
    openTab('timeline')
    if (elementId) focusOn(elementId)
  }
  const startOver = () => {
    if (messages.length > 0 && !window.confirm('Zacząć od nowa? Rozmowa i oś czasu znikną.')) return
    reset()
    setSelectedId(null)
    setTab('chat')
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex h-dvh flex-col bg-canvas lg:flex-row">
        <Rail tab={tab} onChange={openTab} onReset={startOver} className="hidden lg:flex" />

        <header className="flex items-center gap-3 border-b border-line bg-white px-4 py-2.5 lg:hidden">
          <Logo className="size-9" />
          <p className="min-w-0 flex-1 text-[13px] leading-tight font-black text-navy-900">{APP_NAME}</p>
          <button
            type="button"
            onClick={startOver}
            aria-label="Zacznij od nowa"
            className="grid size-9 place-items-center rounded-full text-navy-500"
          >
            <RotateCcw className="size-4" />
          </button>
        </header>

        <main
          className={cn('min-h-0 flex-1 overflow-y-auto', tab === 'chat' && 'hidden lg:block')}
          aria-label={tab === 'about' ? 'Założenia i źródła' : 'Oś czasu'}
        >
          {tab === 'about' ? (
            <AboutPanel timeline={timeline} />
          ) : (
            <>
              <p className="hidden px-8 pt-8 text-xs font-black tracking-widest text-zus-700 uppercase lg:block">
                {APP_NAME}
              </p>
              {timeline && (
                <SummaryTiles
                  timeline={timeline}
                  onSelect={focusOn}
                  className="px-5 pt-5 lg:hidden"
                />
              )}
              <TimelinePanel
                timeline={timeline}
                changed={changed}
                selectedId={selectedId}
                focus={focus}
                onSelect={setSelectedId}
              />
            </>
          )}
        </main>

        <aside
          className={cn(
            'min-h-0 w-full flex-col gap-4 bg-white lg:flex lg:w-[380px] lg:flex-none lg:border-l lg:border-line lg:p-4',
            tab === 'chat' ? 'flex flex-1' : 'hidden',
          )}
          aria-label="Podsumowanie i rozmowa z asystentem"
        >
          {timeline && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: EASE_OUT }}
              className="hidden space-y-4 lg:block"
            >
              <SummaryTiles timeline={timeline} onSelect={focusOn} />
              <ApplicationsList timeline={timeline} selectedId={selectedId} onSelect={focusOn} />
            </motion.div>
          )}
          <div className="min-h-0 flex-1 lg:rounded-3xl lg:bg-canvas">
            <ChatPanel
              messages={messages}
              busy={busy}
              onSend={send}
              onStop={stop}
              onShowTimeline={showOnTimeline}
            />
          </div>
        </aside>

        <BottomNav
          tab={tab}
          onChange={openTab}
          timelineBadge={unseen && tab === 'chat'}
          className="lg:hidden"
        />
      </div>
    </MotionConfig>
  )
}
