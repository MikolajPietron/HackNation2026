import { useCallback, useState } from 'react'
import { AnimatePresence, motion, MotionConfig } from 'motion/react'
import { RotateCcw } from 'lucide-react'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { DocumentsList } from '@/components/documents/DocumentsList'
import { AboutPanel } from '@/components/layout/AboutPanel'
import { BottomNav, Logo, Rail } from '@/components/layout/Navigation'
import type { Tab } from '@/components/layout/Navigation'
import { Onboarding } from '@/components/onboarding/Onboarding'
import { TimelinePanel } from '@/components/timeline/TimelinePanel'
import { useAssistant } from '@/hooks/useAssistant'
import { EASE_IN_OUT, EASE_OUT } from '@/lib/ease'
import { formatLongDate } from '@/lib/dates'
import { childrenLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { SessionStart } from '@/types'

const APP_NAME = 'Zasiłkowy Przewodnik Przyszłego Rodzica'
/** From Tailwind's `lg`: the chat sits next to the timeline. */
const SIDE_BY_SIDE = '(min-width: 64rem)'

export default function App() {
  // Every visit starts on the interview's start screen; this turns true once the parent goes on
  // (finished interview, resumed conversation or chat without the interview).
  const [entered, setEntered] = useState(false)
  const [tab, setTab] = useState<Tab>('chat')
  const [unseen, setUnseen] = useState(false)
  const [unseenChat, setUnseenChat] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focus, setFocus] = useState<{ id: string | null; tick: number }>({ id: null, tick: 0 })

  const focusOn = useCallback((id: string) => {
    setSelectedId(id)
    setFocus((f) => ({ id, tick: f.tick + 1 }))
  }, [])
  // The assistant highlights what it explains. Phones show one panel at a time, so a parent
  // reading the timeline is not scrolled away from it; the tab scrolls to the selection later.
  const assistantFocus = useCallback((id: string) => {
    setSelectedId(id)
    if (window.matchMedia(SIDE_BY_SIDE).matches) setFocus((f) => ({ id, tick: f.tick + 1 }))
  }, [])
  // A recalculated timeline scrolls to what changed but opens nothing: details are on demand.
  const timelineChanged = useCallback((focusId: string | null) => {
    setUnseen(true)
    if (focusId) setFocus((f) => ({ id: focusId, tick: f.tick + 1 }))
  }, [])
  const {
    messages,
    busy,
    restoring,
    send,
    explain,
    stop,
    reset,
    submit,
    load,
    scenario,
    timeline,
    changed,
  } = useAssistant({ onFocus: assistantFocus, onTimeline: timelineChanged })

  // A saved conversation is offered on the start screen; a new interview replaces it only once
  // it is finished.
  const hasSaved = messages.length > 0 || scenario?.role != null
  const savedSummary = timeline
    ? [
        `${timeline.child_born ? 'Data urodzenia' : 'Termin porodu'}: ${formatLongDate(timeline.birth_date)}`,
        timeline.children_count ? childrenLabel(timeline.children_count) : null,
      ]
        .filter(Boolean)
        .join(' · ')
    : 'Zapisana rozmowa z asystentem'

  // Phones show one panel at a time. From `lg` the chat is always on the right and the
  // tab only switches the middle between the timeline and the assumptions.
  const openTab = (next: Tab) => {
    setTab(next)
    setUnseen(false)
    if (next === 'chat') setUnseenChat(false)
    if (next === 'timeline') setFocus((f) => ({ id: selectedId, tick: f.tick + 1 }))
  }
  const showOnTimeline = (elementId: string | null) => {
    openTab('timeline')
    if (elementId) focusOn(elementId)
  }
  const startOver = () => {
    const hasWork = messages.length > 0 || timeline !== null
    if (hasWork && !window.confirm('Zacząć od nowa? Rozmowa i oś czasu znikną.')) return
    reset()
    setSelectedId(null)
    setTab('chat')
    setUnseen(false)
    setUnseenChat(false)
    setEntered(false)
  }
  const finishOnboarding = (start: SessionStart) => {
    load(start)
    setSelectedId(null)
    setTab('timeline')
    setEntered(true)
    // The assistant reacts to the new timeline right away; phones show the timeline, so the
    // chat tab gets a dot.
    setUnseenChat(true)
    void explain()
  }
  const skipOnboarding = () => {
    setTab('chat')
    setEntered(true)
  }
  const resume = () => {
    setTab(timeline ? 'timeline' : 'chat')
    setEntered(true)
    // A timeline nobody has talked about yet: the assistant explains it first.
    if (timeline && messages.length === 0) {
      setUnseenChat(true)
      void explain()
    }
  }

  // Wait for the stored conversation before choosing between the onboarding and the app.
  if (restoring) return <div className="h-dvh bg-white" aria-busy="true" />

  return (
    <MotionConfig reducedMotion="user">
      <AnimatePresence mode="wait">
        {!entered ? (
          <motion.div
            key="onboarding"
            exit={{ opacity: 0, filter: 'blur(6px)', transition: { duration: 0.3, ease: EASE_IN_OUT } }}
          >
            <Onboarding
              submit={submit}
              onDone={finishOnboarding}
              onSkip={skipOnboarding}
              saved={hasSaved ? { summary: savedSummary, onResume: resume } : null}
            />
          </motion.div>
        ) : (
          <motion.div
            key="app"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, ease: EASE_OUT }}
            className="flex h-dvh flex-col bg-canvas lg:flex-row"
          >
            <Rail tab={tab} onChange={openTab} onReset={startOver} className="hidden lg:flex" />

            <header className="flex items-center gap-3 border-b border-line bg-white px-4 py-2.5 lg:hidden">
              <Logo className="size-9" />
              <p className="min-w-0 flex-1 text-[13px] leading-tight font-black text-navy-900">
                {APP_NAME}
              </p>
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
                <AboutPanel scenario={scenario} timeline={timeline} />
              ) : (
                <>
                  <p className="hidden px-8 pt-8 text-xs font-black tracking-widest text-zus-700 uppercase lg:block">
                    {APP_NAME}
                  </p>
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
              aria-label="Dokumenty i rozmowa z asystentem"
            >
              {timeline && timeline.documents.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, ease: EASE_OUT }}
                  className="hidden lg:block"
                >
                  <DocumentsList timeline={timeline} selectedId={selectedId} onSelect={focusOn} />
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
              chatBadge={unseenChat && tab !== 'chat'}
              className="lg:hidden"
            />
          </motion.div>
        )}
      </AnimatePresence>
    </MotionConfig>
  )
}
