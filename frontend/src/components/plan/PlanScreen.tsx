// The plan screen, for phones and wide screens. On top the situation in one sentence and the
// answers to the parents' questions (entitled? how much leave together? what now?); then the one
// decision the family has to make (if any), the "what if" events, the timeline (an editor-style
// axis on wide screens, a vertical list on phones, or a wall calendar) with what lies ahead,
// plans and risks. The why, with the sources, opens on demand ("Dlaczego tak?").
// Wide screens: the assistant is open beside the plan and can be hidden; details are a dialog.
// Phones: the assistant and the details come up as sheets from the bottom (Vaul).
// The windows that lead to one another (an element's details, its money, the request to fill in,
// "Dlaczego tyle?", "Dlaczego tak?") are one window: moving between them keeps breadcrumbs back.
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { CalendarRange, ChevronUp, ExternalLink, RotateCcw, Sparkles, TriangleAlert } from 'lucide-react'
import etat from '@/assets/onboarding/etat.webp'
import mama from '@/assets/onboarding/mama.webp'
import odpoczynek from '@/assets/onboarding/odpoczynek.webp'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { MobileBar } from '@/components/layout/MobileBar'
import { TopBar } from '@/components/layout/TopBar'
import { CasesDialog } from '@/components/cases/CasesDialog'
import { LetterDialog } from '@/components/letters/LetterDialog'
import { BirthCertificate } from '@/components/mocks/BirthCertificate'
import { MObywatelLogin } from '@/components/mocks/MObywatelLogin'
import { ZusDataDialog } from '@/components/mocks/ZusData'
import { ITEM, POP, STEP } from '@/components/onboarding/motion'
import { Sheet } from '@/components/ui/sheet'
import { UndoPill } from '@/components/ui/undo-pill'
import { WindowCrumbs, WindowPage } from '@/components/ui/window-nav'
import { ElementDetails } from '@/components/timeline/ElementDetails'
import { timelineItems } from '@/components/timeline/items'
import type { TimelineItem } from '@/components/timeline/items'
import type { ChangeSet, ChatMessage } from '@/hooks/useAssistant'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { usePlanChange } from '@/hooks/usePlanChange'
import { usePlanSpotlight } from '@/hooks/usePlanSpotlight'
import type { PlanApply } from '@/hooks/usePlanChange'
import { usePlanView } from '@/hooks/usePlanView'
import { useTrail } from '@/hooks/useTrail'
import { EASE_OUT, SPRING_PANEL, SPRING_PRESS } from '@/lib/ease'
import { nextQuestion } from '@/lib/interview'
import type { Choice } from '@/lib/interview'
import { periodName } from '@/lib/plan'
import type { Persona } from '@/lib/mockData'
import { cn } from '@/lib/utils'
import type { InterviewQuestion, Scenario, SessionStart, Timeline } from '@/types'
import { ApplicationForm } from '@/components/applications/ApplicationForm'
import { DocumentsCard } from '@/components/folder/DocumentsCard'
import { PersonalData } from '@/components/folder/PersonalData'
import { ShareDialog } from '@/components/folder/ShareDialog'
import { MoneyCard } from '@/components/money/MoneyCard'
import { ICONS } from '@/lib/icons'
import { MoneyExplanation } from '@/components/money/MoneyExplanation'
import { ChangeBanner } from './ChangeBanner'
import { Dialog } from './Dialog'
import { Explanation } from './Explanation'
import { GoalPlans } from './GoalPlans'
import { LeftOnTable } from './LeftOnTable'
import { MobileTimeline } from './MobileTimeline'
import { NextSteps } from './NextSteps'
import { ParentalEditor } from './ParentalEditor'
import { Overview } from './Overview'
import { RiskRadar } from './RiskRadar'
import { SectionTabs } from './SectionTabs'
import { StressTest } from './StressTest'
import { TimelineCard } from './TimelineCard'
import { ViewSwitch } from './ViewSwitch'
import { YearCalendar } from './YearCalendar'

/** The chat column grows with the screen: roomy on a big monitor, never squeezing the plan on
 *  a small laptop. */
const chatWidth = (viewport: number) => Math.round(Math.min(600, Math.max(440, viewport * 0.34)))
const WIDE = '(min-width: 1024px)'

/** Where the brief sends parents for more (FUNKCJE F29). */
const LINKS = [
  { label: 'ZUS', href: 'https://www.zus.pl' },
  { label: 'Urlop rodzicielski · gov.pl', href: 'https://www.gov.pl/web/rodzina/urlop-rodzicielski' },
  {
    label: 'Rodzicielstwo · PIP',
    href: 'https://www.pip.gov.pl/dla-pracodawcow/porady-prawne/rodzicielstwo',
  },
]

/** A window over the plan; one at a time, the earlier ones as breadcrumbs (hooks/useTrail). */
type Pane =
  | { kind: 'element'; id: string }
  | { kind: 'fill'; id: string }
  | { kind: 'money' }
  | { kind: 'why'; focus?: string }

const samePane = (a: Pane, b: Pane) =>
  a.kind === b.kind && (a.kind === 'element' || a.kind === 'fill' ? a.id === (b as { id: string }).id : true)

const paneKey = (pane: Pane) => (pane.kind === 'element' || pane.kind === 'fill' ? `${pane.kind}:${pane.id}` : pane.kind)

/** A window's name in the breadcrumbs: short, the title is right under them. */
function paneLabel(pane: Pane, items: TimelineItem[]): string {
  switch (pane.kind) {
    case 'money':
      return 'Dlaczego tyle?'
    case 'why':
      return 'Dlaczego tak?'
    case 'fill':
      return 'Wypełnianie wniosku'
    case 'element': {
      const item = items.find((i) => i.id === pane.id)
      if (!item) return 'Szczegóły'
      if (item.kind === 'segment') return periodName(item.element)
      // "Zasiłek mamy: urlop macierzyński po porodzie" -> "Zasiłek mamy" (the period is the crumb before).
      if (item.kind === 'payment') return item.title.split(':')[0]
      return item.title
    }
  }
}

interface Props {
  messages: ChatMessage[]
  busy: boolean
  scenario: Scenario | null
  /** The next interview question from the backend: the cards ask what the assistant asks. */
  question: InterviewQuestion | null
  timeline: Timeline | null
  changed: ChangeSet
  selectedId: string | null
  onSelect: (id: string | null) => void
  onSend: (text: string) => void
  onStop: () => void
  onStartOver: () => void
  /** The logo: back to the start screen, nothing is lost. */
  onHome: () => void
  /** An example case became the plan (a new conversation from its facts). */
  onLoadCase: (start: SessionStart) => void
  /** The plan was changed from the interface (no chat): new scenario and timeline. */
  onUpdate: (start: SessionStart) => void
}

export function PlanScreen({
  messages,
  busy,
  scenario,
  question,
  timeline,
  changed,
  selectedId,
  onSelect,
  onSend,
  onStop,
  onStartOver,
  onHome,
  onLoadCase,
  onUpdate,
}: Props) {
  const wide = useMediaQuery(WIDE)
  const [chatOpen, setChatOpen] = useState(() => window.matchMedia(WIDE).matches)
  const [chatPx, setChatPx] = useState(() => chatWidth(window.innerWidth))
  useEffect(() => {
    const onResize = () => setChatPx(chatWidth(window.innerWidth))
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  /** The explanation window, opened at one point of it or at the top. */
  const [why, setWhy] = useState<{ focus?: string } | null>(null)
  const [view, setView] = usePlanView()
  /** Phones: the whole plan (list or calendar) under what lies ahead, on demand. */
  const [fullPlan, setFullPlan] = useState(false)
  const [moneyOpen, setMoneyOpen] = useState(false)
  /** The request being filled in (a document id). */
  const [fill, setFill] = useState<string | null>(null)
  const fillDocument = timeline?.documents.find((d) => d.id === fill) ?? null
  const [moneyHover, setMoneyHover] = useState<string | null>(null)
  const [overlayRoot, setOverlayRoot] = useState<HTMLDivElement | null>(null)
  const [mock, setMock] = useState<{ text: string; id: number } | null>(null)
  const mockTimer = useRef(0)
  const [persona, setPersona] = useState<Persona | null>(null)
  const [loginOpen, setLoginOpen] = useState(false)
  const [zusOpen, setZusOpen] = useState(false)
  const [casesOpen, setCasesOpen] = useState(false)
  const [letterOpen, setLetterOpen] = useState(false)
  const [certOpen, setCertOpen] = useState(false)
  /** "Twoje dane do wniosków": typed once, kept in this browser. */
  const [personalOpen, setPersonalOpen] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const plan = usePlanChange(scenario, onUpdate)
  /** Every change of the plan is brought into view on the axis; a what-if is shown there too. */
  const {
    anchor: axisAnchor,
    banner,
    dismiss: dismissBanner,
    shown,
    previewing,
    changedIds: axisChanged,
    changeVersion: axisVersion,
    focus: axisFocus,
    show: showEvent,
    endPreview,
    loading: eventLoading,
    error: eventError,
    report: stressReport,
    reportError: stressError,
  } = usePlanSpotlight({ timeline, scenario, changed })
  /** Changes from the interface wait while the assistant is writing (it may be changing the
   *  same plan). */
  const apply: PlanApply = (changes, title, detail) => {
    if (!busy) return plan.apply(changes, title, detail)
    plan.wait('Chwileczkę', 'Asystent jeszcze odpowiada. Zmień plan, gdy skończy.')
    return Promise.resolve(false)
  }
  // After a loss the plan speaks gently and only of what is owed: no planning tools.
  const loss = timeline?.notes.some((n) => n.id === 'loss' || n.text.startsWith('Bardzo nam przykro')) ?? false
  const items = useMemo(() => (shown ? timelineItems(shown) : []), [shown])
  const selected = items.find((item) => item.id === selectedId) ?? null
  const next = scenario && timeline ? nextQuestion(scenario, question) : null

  /** The window open over the plan. The assistant may open an element over another window: the
   *  element wins, and closing it shows the other one again. */
  const pane: Pane | null = !timeline
    ? null
    : fillDocument
      ? { kind: 'fill', id: fillDocument.id }
      : selected
        ? { kind: 'element', id: selected.id }
        : moneyOpen
          ? { kind: 'money' }
          : why
            ? { kind: 'why', focus: why.focus }
            : null
  const trail = useTrail(pane, samePane)
  /** Exactly this window, or none. */
  const show = (to: Pane | null) => {
    setFill(to?.kind === 'fill' ? to.id : null)
    setMoneyOpen(to?.kind === 'money')
    setWhy(to?.kind === 'why' ? { focus: to.focus } : null)
    onSelect(to?.kind === 'element' ? to.id : null)
  }
  /** A window opened from the plan (or closed): it starts without breadcrumbs. */
  const open = (to: Pane | null) => {
    trail.reset()
    show(to)
  }
  /** From one window to the next: the one left becomes a breadcrumb. */
  const go = (to: Pane) => show(trail.forward(to))
  const select = (id: string | null) => open(id ? { kind: 'element', id } : null)
  const openFill = (id: string) => open({ kind: 'fill', id })
  const openWhy = (focus?: string) => open({ kind: 'why', focus })
  const openMoney = () => open({ kind: 'money' })
  const windowLabel =
    pane?.kind === 'element' && selected
      ? selected.title
      : pane?.kind === 'fill' && fillDocument
        ? fillDocument.title
        : pane
          ? paneLabel(pane, items)
          : 'Szczegóły'
  const windowContent =
    pane && timeline ? (
      <WindowPage page={paneKey(pane)} direction={trail.direction}>
        {pane.kind === 'element' && selected ? (
          <ElementDetails
            item={selected}
            timeline={shown ?? timeline}
            onSelect={(id) => go({ kind: 'element', id })}
            onFill={previewing ? undefined : (id) => go({ kind: 'fill', id })}
            onCertificate={() => setCertOpen(true)}
          />
        ) : pane.kind === 'fill' && fillDocument ? (
          // A finding of the request check points at the timeline: its element opens.
          <ApplicationForm
            timeline={timeline}
            document={fillDocument}
            onSelect={(id) => go({ kind: 'element', id })}
            onCertificate={() => setCertOpen(true)}
          />
        ) : pane.kind === 'money' ? (
          <MoneyExplanation timeline={timeline} onSelect={(id) => go({ kind: 'element', id })} />
        ) : pane.kind === 'why' ? (
          <Explanation timeline={timeline} focusId={pane.focus} />
        ) : null}
      </WindowPage>
    ) : null
  const crumbs =
    pane && trail.trail.length > 0 ? (
      <WindowCrumbs
        trail={trail.trail.map((p) => paneLabel(p, items))}
        current={paneLabel(pane, items)}
        onBack={(index) => show(trail.back(index))}
      />
    ) : null

  useEffect(() => () => window.clearTimeout(mockTimer.current), [])

  /** A mocked service was used: say so plainly (FUNKCJE: simulations are clearly marked). */
  const showMock = (text: string) => {
    window.clearTimeout(mockTimer.current)
    setMock({ text, id: Date.now() })
    mockTimer.current = window.setTimeout(() => setMock(null), 3200)
  }

  const checkZus = () => (persona ? setZusOpen(true) : setLoginOpen(true))

  /** A decision card answers the assistant's question; the chat shows the follow-up. */
  const choose = (prompt: string) => {
    setChatOpen(true)
    onSend(prompt)
  }

  const personalData = (
    <PersonalData
      role={scenario?.role ?? 'mother'}
      withFather={timeline?.segments.some((s) => s.lane === 'father') ?? false}
      persona={persona}
      onLogin={() => {
        setPersonalOpen(false)
        setLoginOpen(true)
      }}
      onDone={() => setPersonalOpen(false)}
    />
  )

  const chat = (
    <ChatPanel
      messages={messages}
      busy={busy}
      scenario={scenario}
      question={question}
      onSend={onSend}
      onStop={onStop}
      onShowTimeline={(id) => {
        if (!wide) setChatOpen(false)
        if (id) select(id)
      }}
      planBeside={wide}
      onCollapse={wide ? () => setChatOpen(false) : undefined}
      onVoice={() => showMock('Rozmowę głosową przygotowujemy z ElevenLabs.')}
    />
  )

  return (
    <div className="flex h-dvh flex-col bg-white">
      {wide ? (
        <TopBar
          onHome={onHome}
          persona={persona}
          onLogin={() => setLoginOpen(true)}
          onLogout={() => setPersona(null)}
          onZusData={() => setZusOpen(true)}
          onCases={() => setCasesOpen(true)}
          onLetter={() => setLetterOpen(true)}
        />
      ) : (
        <MobileBar
          onHome={onHome}
          persona={persona}
          onLogin={() => setLoginOpen(true)}
          onLogout={() => setPersona(null)}
          onZusData={() => setZusOpen(true)}
          onCases={() => setCasesOpen(true)}
          onLetter={() => setLetterOpen(true)}
          onAbout={() => openWhy()}
          onStartOver={onStartOver}
          onShare={timeline ? () => setShareOpen(true) : undefined}
        />
      )}

      <div className="flex min-h-0 flex-1">
        <div className="relative flex min-w-0 flex-1 flex-col">
          <main className="scrollbar-soft min-h-0 flex-1 overflow-y-auto lg:[scrollbar-gutter:stable]">
            <motion.div
              variants={STEP}
              initial="enter"
              animate="center"
              className="mx-auto w-full max-w-[1400px] px-4 pt-5 pb-28 lg:px-8 lg:pt-6 lg:pb-16"
            >
              {timeline ? (
                <>
                  <Overview
                    timeline={timeline}
                    scenario={scenario}
                    changed={changed}
                    wide={wide}
                    decisionPending={Boolean(next?.title)}
                    onWhy={openWhy}
                    onSelect={select}
                    onStartOver={onStartOver}
                    onMoney={openMoney}
                    onAsk={choose}
                    onFill={openFill}
                    onShare={() => setShareOpen(true)}
                  />

                  {timeline.warnings.map((warning) => (
                    <motion.p
                      key={warning}
                      variants={ITEM}
                      className="mt-4 flex gap-3 rounded-2xl bg-sun-100 px-4 py-3 text-sun-700 lg:px-5"
                    >
                      <TriangleAlert className="mt-0.5 size-5 shrink-0" />
                      {warning}
                    </motion.p>
                  ))}

                  <AnimatePresence initial={false}>
                    {next?.title && (
                      <Decision
                        key={next.title}
                        title={next.title}
                        subtitle={timeline.notes.find((n) => n.kind === 'choice')?.title ?? null}
                        choices={next.choices}
                        busy={busy}
                        onChoose={choose}
                      />
                    )}
                  </AnimatePresence>

                  <motion.section ref={axisAnchor} variants={ITEM} aria-label="Oś czasu" className="mt-4 scroll-mt-4">
                    <ChangeBanner
                      banner={banner}
                      loading={eventLoading}
                      error={eventError}
                      onSelect={select}
                      onDismiss={dismissBanner}
                      onSwitch={(id) => void showEvent(id)}
                      onHappened={(prompt) => {
                        endPreview()
                        choose(prompt)
                      }}
                    />
                    {wide ? (
                      <TimelineCard
                        timeline={shown ?? timeline}
                        changedIds={axisChanged}
                        changeVersion={axisVersion}
                        selectedId={selectedId}
                        onSelect={select}
                        overlayRoot={overlayRoot}
                        focus={axisFocus}
                        preview={previewing !== null}
                      />
                    ) : (
                      <>
                        <NextSteps
                          timeline={shown ?? timeline}
                          changedIds={axisChanged}
                          changeVersion={axisVersion}
                          hoveredId={null}
                          onHover={() => undefined}
                          onSelect={select}
                        />
                        {/* The whole plan is long on a phone: what lies ahead is above, the rest on demand
                            (opened by itself while an event is previewed on it). */}
                        {fullPlan || previewing !== null ? (
                          <>
                            <div className="mt-8 flex items-center justify-between gap-3">
                              <h3 className="text-lg font-bold text-navy-900">Cały plan</h3>
                              <ViewSwitch view={view} onChange={setView} axisLabel="Lista" />
                            </div>
                            {view === 'axis' ? (
                              <MobileTimeline
                                timeline={shown ?? timeline}
                                changedIds={axisChanged}
                                changeVersion={axisVersion}
                                selectedId={selectedId}
                                onSelect={select}
                              />
                            ) : (
                              <div className="mt-4">
                                <YearCalendar timeline={shown ?? timeline} onSelect={select} />
                              </div>
                            )}
                            <button
                              type="button"
                              onClick={() => setFullPlan(false)}
                              className="mt-4 flex h-11 w-full items-center justify-center gap-1.5 rounded-full border border-line text-sm font-bold text-navy-700 transition-colors hover:bg-navy-50"
                            >
                              <ChevronUp className="size-4" /> Zwiń cały plan
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setFullPlan(true)}
                            className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-full border border-line bg-white text-sm font-bold text-navy-900 transition-colors hover:bg-navy-50"
                          >
                            <CalendarRange className="size-4 text-zus-700" /> Pokaż cały plan: oś i kalendarz
                          </button>
                        )}
                      </>
                    )}
                  </motion.section>

                  <motion.div variants={ITEM} className="mt-5">
                    <MoneyCard
                      timeline={timeline}
                      scenario={scenario}
                      hoveredId={moneyHover}
                      onHover={setMoneyHover}
                      onSelect={select}
                      onWhy={openMoney}
                      onApply={apply}
                    />
                  </motion.div>

                  <motion.div variants={ITEM} className="mt-5">
                    <DocumentsCard
                      timeline={timeline}
                      scenario={scenario}
                      onFill={openFill}
                      onSelect={select}
                      onPersonal={() => setPersonalOpen(true)}
                    />
                  </motion.div>

                  {!loss && (
                    <SectionTabs
                      title="Dopasujcie plan"
                      subtitle="Podzielcie urlop, wybierzcie plan pod swój cel i sprawdźcie, czego jeszcze nie wykorzystujecie."
                      tabs={[
                        ...(scenario && !timeline.taken_in && timeline.segments.some((s) => s.lane === 'father' && s.id.startsWith('parental'))
                          ? [{ id: 'split', label: 'Podział urlopu', icon: ICONS.wozek, content: <ParentalEditor scenario={scenario} onApply={apply} /> }]
                          : []),
                        { id: 'plans', label: 'Plany dla celu', icon: ICONS.skarbonka, content: <GoalPlans scenario={scenario} onApply={apply} /> },
                        ...(timeline.left_on_table.length > 0
                          ? [
                              {
                                id: 'left',
                                label: 'Do wykorzystania',
                                icon: ICONS.kalendarz,
                                content: (
                                  <LeftOnTable
                                    timeline={timeline}
                                    scenario={scenario}
                                    onSelect={select}
                                    onFill={openFill}
                                    onApply={apply}
                                    onCompare={() =>
                                      document.getElementById('rate-choice')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                                    }
                                  />
                                ),
                              },
                            ]
                          : []),
                      ]}
                    />
                  )}

                  {!loss && (
                    <SectionTabs
                      title="Co może się zmienić"
                      subtitle="Co zmieni się w planie, gdy coś się wydarzy, i na co uważać, żeby nie stracić zasiłku."
                      tabs={[
                        {
                          id: 'whatif',
                          label: 'Co jeśli…',
                          icon: ICONS.parasol,
                          content: (
                            <StressTest
                              report={stressReport}
                              error={stressError}
                              active={previewing?.id ?? null}
                              loading={eventLoading}
                              onPreview={(id) => void showEvent(id)}
                            />
                          ),
                        },
                        {
                          id: 'risks',
                          label: 'Na co uważać',
                          icon: ICONS.zlecenie,
                          content: <RiskRadar timeline={timeline} scenario={scenario} onCheckZus={checkZus} onWhy={openWhy} />,
                        },
                      ]}
                    />
                  )}
                  <Footer />
                </>
              ) : (
                <Empty onStartOver={onStartOver} />
              )}
            </motion.div>
          </main>

          <div ref={setOverlayRoot} className="pointer-events-none absolute inset-0 z-20" />

          {wide && (
            <AnimatePresence>
              {pane && (
                <Dialog key="window" label={windowLabel} onClose={() => open(null)} top={crumbs}>
                  {windowContent}
                </Dialog>
              )}
              {shareOpen && (
                <Dialog key="share" label="Udostępnij plan" onClose={() => setShareOpen(false)}>
                  <ShareDialog />
                </Dialog>
              )}
              {personalOpen && (
                <Dialog key="personal" label="Twoje dane do wniosków" onClose={() => setPersonalOpen(false)}>
                  {personalData}
                </Dialog>
              )}
            </AnimatePresence>
          )}

          <AnimatePresence>
            {!chatOpen && (
              <motion.button
                key="open-chat"
                type="button"
                onClick={() => setChatOpen(true)}
                initial={{ opacity: 0, y: 16, scale: 0.94 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 16, scale: 0.94 }}
                whileTap={{ scale: 0.96, transition: SPRING_PRESS }}
                transition={SPRING_PANEL}
                className="absolute right-4 bottom-4 z-20 flex h-14 items-center gap-3 rounded-full bg-zus-600 pr-5 pl-5 font-bold text-white shadow-[0_18px_40px_-18px_rgb(2_90_40/0.8)] transition-colors hover:bg-zus-700 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2 focus-visible:outline-none lg:right-8 lg:bottom-8"
              >
                <Sparkles className="size-5" />
                Zapytaj asystenta
                <span className="rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-black tracking-wide">
                  AI
                </span>
                {busy && <span className="size-2 rounded-full bg-sun-300 motion-safe:animate-pulse" />}
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        {wide && (
          <AnimatePresence initial={false}>
            {chatOpen && (
              <motion.aside
                key="chat"
                aria-label="Rozmowa z asystentem"
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: chatPx, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={SPRING_PANEL}
                className="h-full shrink-0 overflow-hidden border-l border-line bg-white"
              >
                <div className="h-full py-2" style={{ width: chatPx }}>
                  {chat}
                </div>
              </motion.aside>
            )}
          </AnimatePresence>
        )}
      </div>

      {!wide && (
        <>
          <Sheet open={chatOpen} onOpenChange={setChatOpen} title="Rozmowa z asystentem" fullHeight>
            {chat}
          </Sheet>
          <Sheet open={pane !== null} onOpenChange={(isOpen) => !isOpen && open(null)} title={windowLabel} top={crumbs}>
            {windowContent}
          </Sheet>
          <Sheet open={shareOpen} onOpenChange={setShareOpen} title="Udostępnij plan">
            <ShareDialog />
          </Sheet>
          <Sheet open={personalOpen} onOpenChange={setPersonalOpen} title="Twoje dane do wniosków">
            {personalData}
          </Sheet>
        </>
      )}

      <MObywatelLogin
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        onLogin={(p) => {
          setPersona(p)
          setLoginOpen(false)
          setZusOpen(true)
        }}
      />
      <ZusDataDialog
        persona={persona}
        open={zusOpen}
        onClose={() => setZusOpen(false)}
        onMock={showMock}
        timeline={timeline}
        scenario={scenario}
        onApply={apply}
        onWhy={(focus) => {
          setZusOpen(false)
          openWhy(focus)
        }}
      />
      <CasesDialog open={casesOpen} onClose={() => setCasesOpen(false)} onLoaded={onLoadCase} />
      <BirthCertificate open={certOpen} onClose={() => setCertOpen(false)} />
      <LetterDialog open={letterOpen} onClose={() => setLetterOpen(false)} timeline={timeline} onSelect={select} />

      <UndoPill change={plan.change} onUndo={() => void plan.undo()} onDismiss={plan.dismiss} />

      <AnimatePresence>
        {mock && (
          <motion.div
            key={mock.id}
            role="status"
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, transition: { duration: 0.15 } }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            className="fixed inset-x-4 bottom-24 z-[60] flex items-center gap-3 rounded-3xl bg-navy-900 py-3 pr-5 pl-3 text-sm font-bold text-white shadow-[0_18px_40px_-18px_rgb(26_36_56/0.6)] lg:inset-x-auto lg:bottom-6 lg:left-1/2 lg:-translate-x-1/2 lg:rounded-full"
          >
            <span className="shrink-0 rounded-full bg-white/15 px-2.5 py-0.5 text-[11px] tracking-wide">
              atrapa
            </span>
            {mock.text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/** The decision the family has to make next, compact so the timeline keeps the room. */
function Decision({
  title,
  subtitle,
  choices,
  busy,
  onChoose,
}: {
  title: string
  subtitle: string | null
  choices: Choice[]
  busy: boolean
  onChoose: (prompt: string) => void
}) {
  const [picked, setPicked] = useState<string | null>(null)
  return (
    <motion.section
      variants={ITEM}
      initial="enter"
      animate="center"
      exit={{ opacity: 0, filter: 'blur(4px)', transition: { duration: 0.2 } }}
      className="mt-5 flex flex-col gap-3 rounded-3xl border border-line p-3 lg:flex-row lg:items-center lg:gap-5 lg:py-3 lg:pr-3 lg:pl-6"
    >
      <div className="min-w-0 flex-1 px-2 pt-1 lg:p-0">
        <h2 className="text-lg leading-tight font-bold text-navy-900">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-navy-500">{subtitle}</p>}
      </div>
      <div role="radiogroup" aria-label={title} className="grid grid-cols-2 gap-2 lg:flex">
        {choices.map((choice) => {
          const selected = picked === choice.prompt
          return (
            <motion.button
              key={choice.prompt}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => {
                if (busy) return
                setPicked(choice.prompt)
                onChoose(choice.prompt)
              }}
              whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
              className={cn(
                'group flex flex-col items-start gap-1 rounded-2xl border bg-white p-2 text-left lg:flex-row lg:items-center lg:gap-3 lg:py-1.5 lg:pr-5 lg:pl-1.5',
                'transition-[border-color,background-color,box-shadow,opacity] duration-200',
                'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
                selected
                  ? 'border-zus-600 bg-zus-50 shadow-[0_0_0_1px_var(--color-zus-600)]'
                  : 'border-line hover:border-navy-200',
                busy && picked !== null && !selected && 'opacity-40',
              )}
            >
              <img
                src={choice.image === 'rest' ? odpoczynek : etat}
                alt=""
                draggable={false}
                className="size-12 object-contain transition-transform duration-300 ease-[cubic-bezier(0.23,1,0.32,1)] select-none group-hover:-translate-y-0.5 lg:size-14"
              />
              <span className="px-1 pb-1 lg:p-0">
                <span className="block text-sm leading-snug font-bold text-navy-900 lg:text-base">
                  {choice.label}
                </span>
                <span className="block text-xs text-navy-500 lg:text-sm">{choice.hint}</span>
              </span>
            </motion.button>
          )
        })}
      </div>
    </motion.section>
  )
}

/** Links from the brief (the admin panel is in the top bar). */
function Footer() {
  return (
    <motion.footer
      variants={ITEM}
      className="mt-14 flex flex-col gap-4 border-t border-line pt-6 text-sm lg:flex-row lg:items-center"
    >
      <p className="font-bold text-navy-900">Więcej informacji</p>
      <ul className="flex flex-wrap gap-2">
        {LINKS.map((link) => (
          <li key={link.href}>
            <a
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 rounded-full border border-line px-3.5 py-2 font-bold text-navy-700 transition-[border-color,background-color] duration-150 hover:border-navy-200 hover:bg-navy-50"
            >
              {link.label}
              <ExternalLink className="size-3.5 text-navy-400" />
            </a>
          </li>
        ))}
      </ul>
    </motion.footer>
  )
}

function Empty({ onStartOver }: { onStartOver: () => void }) {
  return (
    <section className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <motion.img variants={POP} src={mama} alt="" className="w-24 select-none" draggable={false} />
      <motion.h1 variants={ITEM} className="mt-6 text-3xl font-bold tracking-tight text-navy-900 lg:text-4xl">
        Zacznijmy od daty
      </motion.h1>
      <motion.p variants={ITEM} className="mt-3 max-w-md text-lg text-pretty text-navy-500">
        Napisz asystentowi, kiedy jest termin porodu albo kiedy urodziło się dziecko. Plan pojawi
        się tutaj.
      </motion.p>
      <motion.div variants={ITEM} className="mt-6">
        <GhostButton onClick={onStartOver}>
          <RotateCcw className="size-4" /> Odpowiedz na kilka pytań
        </GhostButton>
      </motion.div>
    </section>
  )
}

function GhostButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-10 items-center gap-2 rounded-full px-4 text-sm font-bold text-navy-500 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
    >
      {children}
    </button>
  )
}
