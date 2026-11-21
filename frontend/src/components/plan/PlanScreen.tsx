// The plan screen, for phones and wide screens. The timeline is the main thing, so everything
// above it is one line: how long the leave is and when. Then the one decision the family has to
// make (if any), the "what if" events, the timeline (an editor-style axis on wide screens, a
// vertical line on phones), plans and risks. Legal text and sources only on demand.
// Wide screens: the assistant is open beside the plan and can be hidden; details are a dialog.
// Phones: the assistant and the details come up as sheets from the bottom (Vaul).
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ExternalLink, RotateCcw, Sparkles, TriangleAlert } from 'lucide-react'
import etat from '@/assets/onboarding/etat.webp'
import mama from '@/assets/onboarding/mama.webp'
import odpoczynek from '@/assets/onboarding/odpoczynek.webp'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { MobileBar } from '@/components/layout/MobileBar'
import { TopBar } from '@/components/layout/TopBar'
import { CasesDialog } from '@/components/mocks/Cases'
import { MObywatelLogin } from '@/components/mocks/MObywatelLogin'
import { ZusDataDialog } from '@/components/mocks/ZusData'
import { ITEM, POP, STEP } from '@/components/onboarding/motion'
import { Sheet } from '@/components/ui/sheet'
import { TextStates } from '@/components/ui/text-states'
import { CaseNotes } from '@/components/timeline/CaseNotes'
import { ElementDetails } from '@/components/timeline/ElementDetails'
import { timelineItems } from '@/components/timeline/items'
import type { ChangeSet, ChatMessage } from '@/hooks/useAssistant'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { formatLongDate, formatShortDate } from '@/lib/dates'
import { EASE_OUT, SPRING_PANEL, SPRING_PRESS } from '@/lib/ease'
import { nextQuestion } from '@/lib/interview'
import type { Choice } from '@/lib/interview'
import type { Persona } from '@/lib/mockData'
import { plural, sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { InterviewQuestion, Scenario, Timeline } from '@/types'
import { Dialog } from './Dialog'
import { GoalPlans } from './GoalPlans'
import { MobileTimeline } from './MobileTimeline'
import { RiskRadar } from './RiskRadar'
import { TimelineCard } from './TimelineCard'
import { WhatIf } from './WhatIf'

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
}: Props) {
  const wide = useMediaQuery(WIDE)
  const [chatOpen, setChatOpen] = useState(() => window.matchMedia(WIDE).matches)
  const [chatPx, setChatPx] = useState(() => chatWidth(window.innerWidth))
  useEffect(() => {
    const onResize = () => setChatPx(chatWidth(window.innerWidth))
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  const [about, setAbout] = useState(false)
  const [overlayRoot, setOverlayRoot] = useState<HTMLDivElement | null>(null)
  const [mock, setMock] = useState<{ text: string; id: number } | null>(null)
  const mockTimer = useRef(0)
  const [persona, setPersona] = useState<Persona | null>(null)
  const [loginOpen, setLoginOpen] = useState(false)
  const [zusOpen, setZusOpen] = useState(false)
  const [casesOpen, setCasesOpen] = useState(false)
  const items = useMemo(() => (timeline ? timelineItems(timeline) : []), [timeline])
  const changedIds = useMemo(() => new Set(changed.ids), [changed])
  const selected = items.find((item) => item.id === selectedId) ?? null
  const next = scenario && timeline ? nextQuestion(scenario, question) : null

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
        if (id) onSelect(id)
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
          onMock={showMock}
          persona={persona}
          onLogin={() => setLoginOpen(true)}
          onLogout={() => setPersona(null)}
          onZusData={() => setZusOpen(true)}
          onCases={() => setCasesOpen(true)}
        />
      ) : (
        <MobileBar
          persona={persona}
          onLogin={() => setLoginOpen(true)}
          onLogout={() => setPersona(null)}
          onZusData={() => setZusOpen(true)}
          onCases={() => setCasesOpen(true)}
          onAbout={() => setAbout(true)}
          onStartOver={onStartOver}
          onMock={showMock}
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
                  <Summary
                    timeline={timeline}
                    wide={wide}
                    onAbout={() => setAbout(true)}
                    onStartOver={onStartOver}
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

                  {/* The case explained in plain words, short until opened (CLAUDE.md,
                      "Wyjaśnianie przypadku"); the points an answer changed light up. */}
                  <motion.div variants={ITEM} className="mt-5 @container">
                    <CaseNotes notes={timeline.notes} changed={changed} />
                  </motion.div>

                  <motion.div variants={ITEM} className="mt-5">
                    <WhatIf scenario={scenario} busy={busy} onSend={choose} onMock={showMock} />
                  </motion.div>

                  <motion.section variants={ITEM} aria-label="Oś czasu" className="mt-4">
                    {wide ? (
                      <TimelineCard
                        timeline={timeline}
                        changedIds={changedIds}
                        changeVersion={changed.version}
                        selectedId={selectedId}
                        onSelect={onSelect}
                        overlayRoot={overlayRoot}
                      />
                    ) : (
                      <MobileTimeline
                        timeline={timeline}
                        changedIds={changedIds}
                        changeVersion={changed.version}
                        selectedId={selectedId}
                        onSelect={onSelect}
                      />
                    )}
                  </motion.section>

                  <GoalPlans onMock={showMock} />
                  <RiskRadar scenario={scenario} onCheckZus={checkZus} />
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
              {selected && timeline && (
                <Dialog key="details" label={selected.title} onClose={() => onSelect(null)}>
                  <ElementDetails key={selected.id} item={selected} timeline={timeline} onSelect={onSelect} />
                </Dialog>
              )}
              {about && timeline && (
                <Dialog key="about" label="Jak to liczymy" onClose={() => setAbout(false)}>
                  <HowWeCount timeline={timeline} />
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
          <Sheet
            open={selected !== null && timeline !== null}
            onOpenChange={(open) => !open && onSelect(null)}
            title={selected?.title ?? 'Szczegóły'}
          >
            {selected && timeline && (
              <ElementDetails key={selected.id} item={selected} timeline={timeline} onSelect={onSelect} />
            )}
          </Sheet>
          <Sheet open={about && timeline !== null} onOpenChange={setAbout} title="Jak to liczymy">
            {timeline && <HowWeCount timeline={timeline} />}
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
      <ZusDataDialog persona={persona} open={zusOpen} onClose={() => setZusOpen(false)} onMock={showMock} />
      <CasesDialog open={casesOpen} onClose={() => setCasesOpen(false)} onMock={showMock} />

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

/** The answer in one line: how long the mother's leave is and when. */
function Summary({
  timeline,
  wide,
  onAbout,
  onStartOver,
}: {
  timeline: Timeline
  wide: boolean
  onAbout: () => void
  onStartOver: () => void
}) {
  const leave = timeline.segments.filter((s) => s.lane === 'mother' && s.tone === 'leave')
  const days = leave.reduce((sum, s) => sum + s.days, 0)
  const start = leave.map((s) => s.start).sort()[0]
  const end = leave.map((s) => s.end).sort().at(-1)
  const amount =
    days === 0
      ? 'Twój plan'
      : days % 7 === 0
        ? `${days / 7} ${plural(days / 7, 'tydzień', 'tygodnie', 'tygodni')}`
        : `${days} ${plural(days, 'dzień', 'dni', 'dni')}`
  const range =
    start && end
      ? `${formatShortDate(start)} – ${formatShortDate(end)}`
      : `${timeline.child_born ? 'Data urodzenia' : 'Termin porodu'}: ${formatLongDate(timeline.birth_date)}`

  return (
    <motion.header variants={ITEM} className="flex flex-wrap items-end gap-x-6 gap-y-2">
      <div className="min-w-0">
        <p className="text-sm font-bold text-zus-700">Urlop macierzyński</p>
        <h1 className="mt-0.5 flex flex-wrap items-baseline gap-x-3 text-3xl leading-tight font-bold tracking-tight text-navy-900 lg:text-4xl">
          <TextStates text={amount} />
          <span className="text-base font-bold tracking-normal text-navy-400 lg:text-xl">
            <TextStates text={range} />
          </span>
        </h1>
      </div>
      {wide && (
        <div className="ml-auto flex items-center gap-1">
          <GhostButton onClick={onAbout}>Jak to liczymy?</GhostButton>
          <GhostButton onClick={onStartOver}>
            <RotateCcw className="size-4" /> Od nowa
          </GhostButton>
        </div>
      )}
    </motion.header>
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

/** The case explanation and the calculator's assumptions, out of the way until asked for. */
function HowWeCount({ timeline }: { timeline: Timeline }) {
  return (
    <div className="space-y-6 text-navy-700">
      <header className="pr-10">
        <h2 className="text-2xl font-bold tracking-tight text-navy-900">Jak to liczymy</h2>
        <p className="mt-2">
          Daty liczy kalkulator reguł, bez AI. Rozmowę prowadzi asystent AI. Każdy element osi ma
          dosłowny cytat z Przewodnika ZUS albo Kodeksu pracy.
        </p>
      </header>
      {timeline.notes.length > 0 && (
        <ul className="space-y-4">
          {timeline.notes.map((note) => (
            <li key={note.id}>
              <p className="font-bold text-navy-900">{note.title}</p>
              <p className="mt-0.5 leading-relaxed">{note.text}</p>
              {note.sources.length > 0 && (
                <p className="mt-1 text-sm text-navy-400">
                  {[...new Set(note.sources.map(sourceLabel))].join(' · ')}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      {timeline.assumptions.length > 0 && (
        <section>
          <h3 className="font-bold text-navy-900">Założenia kalkulatora</h3>
          <ul className="mt-2 space-y-1.5">
            {timeline.assumptions.map((text) => (
              <li key={text} className="flex gap-3">
                <span className="mt-[0.6em] size-1.5 shrink-0 rounded-full bg-navy-200" />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

/** Links from the brief, and the way into the admin panel. */
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
      <a href="/admin" className="font-bold text-navy-500 hover:text-navy-900 lg:ml-auto">
        Panel administracyjny (demo)
      </a>
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
