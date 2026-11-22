import { useCallback, useRef, useState } from 'react'
import { AnimatePresence, motion, MotionConfig } from 'motion/react'
import { AdminScreen } from '@/components/admin/AdminScreen'
import { ReportScreen } from '@/components/report/ReportScreen'
import { Onboarding } from '@/components/onboarding/Onboarding'
import { PlanScreen } from '@/components/plan/PlanScreen'
import { SharedPlan } from '@/components/plan/SharedPlan'
import { useAssistant } from '@/hooks/useAssistant'
import { formatLongDate } from '@/lib/dates'
import { EASE_IN_OUT, EASE_OUT } from '@/lib/ease'
import { childrenLabel } from '@/lib/ui'
import type { SessionStart } from '@/types'

/** `/admin` is the parameters panel, `/raport` the agreement report; the rest is the parents' app. */
export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      {window.location.pathname.startsWith('/admin') ? (
        <AdminScreen />
      ) : window.location.pathname.startsWith('/raport') ? (
        <ReportScreen />
      ) : window.location.pathname.startsWith('/plan/') ? (
        <SharedPlan token={window.location.pathname.split('/')[2] ?? ''} />
      ) : (
        <ParentsApp />
      )}
    </MotionConfig>
  )
}

function ParentsApp() {
  // Every visit starts on the interview's start screen; this turns true once the parent goes on
  // (finished interview, resumed plan or chat without the interview).
  const [entered, setEntered] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  // While the assistant explains a new timeline by itself, the element it points at is not
  // opened: the parent has just arrived at the plan and should see it first.
  const explaining = useRef(false)

  // The assistant explains an element: its details open. A recalculated timeline only
  // highlights the change; details stay on demand.
  const focusOn = useCallback((id: string) => {
    if (!explaining.current) setSelectedId(id)
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
    update,
    scenario,
    question,
    timeline,
    changed,
  } = useAssistant({ onFocus: focusOn })

  /** The assistant reacts to a timeline that appeared outside the chat. */
  const explainTimeline = () => {
    explaining.current = true
    void explain().finally(() => {
      explaining.current = false
    })
  }
  const sendMessage = (text: string) => {
    explaining.current = false
    void send(text)
  }

  // A saved conversation is offered on the start screen; a new interview replaces it only once
  // it is finished.
  const hasSaved = messages.length > 0 || scenario?.role != null
  const savedSummary = timeline
    ? [
        `${timeline.taken_in ? 'Przyjęcie dziecka' : timeline.child_born ? 'Data urodzenia' : 'Termin porodu'}: ${formatLongDate(timeline.birth_date)}`,
        timeline.children_count ? childrenLabel(timeline.children_count) : null,
      ]
        .filter(Boolean)
        .join(' · ')
    : 'Zapisana rozmowa z asystentem'

  const startOver = () => {
    const hasWork = messages.length > 0 || timeline !== null
    if (hasWork && !window.confirm('Zacząć od nowa? Rozmowa i oś czasu znikną.')) return
    reset()
    setSelectedId(null)
    setEntered(false)
  }
  const finishOnboarding = (start: SessionStart) => {
    load(start)
    setSelectedId(null)
    setEntered(true)
    // The assistant reacts to the new timeline right away.
    explainTimeline()
  }
  const resume = () => {
    setEntered(true)
    // A timeline nobody has talked about yet: the assistant explains it first.
    if (timeline && messages.length === 0) explainTimeline()
  }

  // Wait for the stored conversation before choosing between the start screen and the plan.
  if (restoring) return <div className="h-dvh bg-white" aria-busy="true" />

  return (
    <AnimatePresence mode="wait">
      {!entered ? (
        <motion.div
          key="onboarding"
          exit={{ opacity: 0, filter: 'blur(6px)', transition: { duration: 0.3, ease: EASE_IN_OUT } }}
        >
          <Onboarding
            submit={submit}
            onDone={finishOnboarding}
            onSkip={() => setEntered(true)}
            saved={hasSaved ? { summary: savedSummary, onResume: resume } : null}
          />
        </motion.div>
      ) : (
        <motion.div
          key="plan"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, ease: EASE_OUT }}
        >
          <PlanScreen
            messages={messages}
            busy={busy}
            scenario={scenario}
            question={question}
            timeline={timeline}
            changed={changed}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onSend={sendMessage}
            onStop={stop}
            onStartOver={startOver}
            onLoadCase={finishOnboarding}
            onUpdate={update}
          />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
