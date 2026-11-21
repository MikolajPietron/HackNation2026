import { useCallback, useState } from 'react'
import { AnimatePresence, motion, MotionConfig } from 'motion/react'
import { AdminScreen } from '@/components/admin/AdminScreen'
import { Onboarding } from '@/components/onboarding/Onboarding'
import { PlanScreen } from '@/components/plan/PlanScreen'
import { useAssistant } from '@/hooks/useAssistant'
import { EASE_IN_OUT, EASE_OUT } from '@/lib/ease'
import type { SessionStart } from '@/types'

/** `/admin` is the parameters panel; everything else is the parents' app. */
export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      {window.location.pathname.startsWith('/admin') ? <AdminScreen /> : <ParentsApp />}
    </MotionConfig>
  )
}

function ParentsApp() {
  const [skippedOnboarding, setSkippedOnboarding] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // The assistant explains an element: its details open. A recalculated timeline only
  // highlights the change; details stay on demand.
  const focusOn = useCallback((id: string) => setSelectedId(id), [])
  const { messages, busy, restoring, send, stop, reset, submit, load, scenario, timeline, changed } =
    useAssistant({ onFocus: focusOn })

  // The onboarding runs until its answers are saved: it always saves the role, the chat never
  // does. A conversation that has started, or a skipped onboarding, goes straight to the plan.
  const onboardingSaved = scenario?.role != null
  const onboarding = !skippedOnboarding && messages.length === 0 && !onboardingSaved

  const startOver = () => {
    const hasWork = messages.length > 0 || timeline !== null
    if (hasWork && !window.confirm('Zacząć od nowa? Rozmowa i oś czasu znikną.')) return
    reset()
    setSelectedId(null)
    setSkippedOnboarding(false)
  }
  const finishOnboarding = (start: SessionStart) => {
    load(start)
    setSelectedId(null)
  }

  // Wait for the stored conversation before choosing between the onboarding and the plan.
  if (restoring) return <div className="h-dvh bg-white" aria-busy="true" />

  return (
    <AnimatePresence mode="wait">
      {onboarding ? (
        <motion.div
          key="onboarding"
          exit={{ opacity: 0, filter: 'blur(6px)', transition: { duration: 0.3, ease: EASE_IN_OUT } }}
        >
          <Onboarding submit={submit} onDone={finishOnboarding} onSkip={() => setSkippedOnboarding(true)} />
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
            timeline={timeline}
            changed={changed}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onSend={send}
            onStop={stop}
            onStartOver={startOver}
          />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
