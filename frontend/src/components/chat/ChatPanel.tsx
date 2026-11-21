// The conversation with the assistant, kept quiet so the plan stays the main thing: no header,
// light user bubbles, plain assistant text, sources as small pills, changes to the timeline as
// one card that links back to it, and the next question's answers as quick replies.
// The AI label the challenge asks for sits in the composer.
import { useEffect, useRef } from 'react'
import { ChevronRight, PanelRightClose } from 'lucide-react'
import Markdown from 'react-markdown'
import type { Components } from 'react-markdown'
import { PromptComposer } from '@/components/ui/prompt-composer'
import { TextStates } from '@/components/ui/text-states'
import type { ChatMessage, MessagePart } from '@/hooks/useAssistant'
import { nextQuestion } from '@/lib/interview'
import { toolLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { Scenario } from '@/types'

// Without the onboarding the chat asks for the date first.
const START_SUGGESTIONS = [
  'Podam przewidywaną datę porodu',
  'Dziecko już się urodziło',
  'Spodziewamy się bliźniąt',
]

/** Tools that change the plan (the others only point at it). */
const PLAN_TOOLS = new Set([
  'set_due_date',
  'set_birth_date',
  'set_children_count',
  'set_leave_before_birth',
  'set_medical_certificate',
])

const MARKDOWN: Components = {
  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  strong: ({ children }) => <strong className="font-bold text-navy-900">{children}</strong>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="font-bold text-zus-700 underline-offset-2 hover:underline">
      {children}
    </a>
  ),
}

/** "(Przewodnik ZUS, s. 5; Kodeks pracy, art. 183¹ § 2)" in the text becomes pills below it. */
const CITATION = /\s*\(([^()]*(?:Przewodnik|Kodeks pracy)[^()]*)\)/g

function splitCitations(text: string): { text: string; sources: string[] } {
  const sources: string[] = []
  const clean = text.replace(CITATION, (_, inner: string) => {
    for (const part of inner.split(';')) {
      const label = part
        .trim()
        .replace(/^Przewodnik ZUS,?\s*/, 'Przewodnik · ')
        .replace(/^Kodeks pracy,?\s*/, 'KP · ')
      if (label && !sources.includes(label)) sources.push(label)
    }
    return ''
  })
  return { text: clean, sources }
}

interface Props {
  messages: ChatMessage[]
  busy: boolean
  /** What the onboarding saved: greet with the next question instead of asking for the date. */
  scenario: Scenario | null
  onSend: (text: string) => void
  onStop: () => void
  /** Jump to the timeline (on phones it is a separate tab), optionally to one element. */
  onShowTimeline: (elementId: string | null) => void
  /** Desktop plan screen: the plan is beside the chat, and the chat can be hidden. */
  planBeside?: boolean
  onCollapse?: () => void
  /** Voice input (ElevenLabs later); without it there is no microphone. */
  onVoice?: () => void
}

export function ChatPanel({
  messages,
  busy,
  scenario,
  onSend,
  onStop,
  onShowTimeline,
  planBeside = false,
  onCollapse,
  onVoice,
}: Props) {
  const listRef = useRef<HTMLDivElement>(null)
  const dateKnown = scenario !== null && (scenario.due_date ?? scenario.birth_date) !== null
  const next = scenario && dateKnown ? nextQuestion(scenario) : null
  const last = messages.at(-1)
  const replies =
    !busy && (messages.length === 0 || (last?.role === 'assistant' && last.status === 'done'))
      ? next
        ? next.prompts
        : START_SUGGESTIONS
      : []

  useEffect(() => {
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages, replies.length])

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      {onCollapse && (
        <button
          type="button"
          onClick={onCollapse}
          aria-label="Schowaj asystenta"
          title="Schowaj asystenta"
          className="absolute top-2 right-3 z-10 grid size-9 place-items-center rounded-full text-navy-300 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.94] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
        >
          <PanelRightClose className="size-4" />
        </button>
      )}

      <div
        ref={listRef}
        className="scrollbar-soft fade-y min-h-0 flex-1 space-y-5 overflow-y-auto px-5 pt-6 pb-4"
        aria-live="polite"
      >
        {messages.length === 0 && (
          <div className="motion-safe:animate-msg-in">
            <p className="text-[15px] leading-relaxed text-navy-500">
              {next
                ? planBeside
                  ? 'Twój plan widzisz obok. Kolejne pytanie:'
                  : 'Mam Twoje odpowiedzi. Kolejne pytanie:'
                : 'Cześć! Zaplanujmy urlop macierzyński. Na początek:'}
            </p>
            <p className="mt-1 text-lg leading-snug font-bold text-navy-900">
              {next
                ? next.question.charAt(0).toUpperCase() + next.question.slice(1)
                : 'Kiedy jest przewidywany poród albo kiedy urodziło się dziecko?'}
            </p>
          </div>
        )}

        {messages.map((message) =>
          message.role === 'user' ? (
            <UserMessage key={message.id} message={message} />
          ) : (
            <AssistantMessage key={message.id} message={message} onShowTimeline={onShowTimeline} />
          ),
        )}

        {replies.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {replies.map((prompt, index) => (
              <button
                key={prompt}
                type="button"
                onClick={() => onSend(prompt)}
                style={{ animationDelay: `${index * 50}ms` }}
                className="rounded-full border border-line bg-white px-3.5 py-2 text-left text-sm font-bold text-navy-700 transition-[border-color,background-color,color,transform] duration-150 hover:border-zus-300 hover:bg-zus-50 hover:text-zus-900 active:scale-[0.96] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none motion-safe:animate-msg-in"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="px-3 pb-3">
        <PromptComposer
          placeholder="Zapytaj o swój plan…"
          onSend={onSend}
          onStop={onStop}
          isGenerating={busy}
          onVoice={onVoice}
          badge={
            <span
              title="Asystent AI. Daty liczy kalkulator reguł, nie AI."
              className="grid h-7 place-items-center rounded-full bg-zus-50 px-2.5 text-[11px] font-black tracking-wide text-zus-700"
            >
              AI
            </span>
          }
        />
        <p className="mt-2 text-center text-[11px] text-navy-400">
          AI może się mylić. Daty liczy kalkulator reguł, nie AI.
        </p>
      </div>
    </div>
  )
}

function UserMessage({ message }: { message: ChatMessage }) {
  const text = message.parts.map((p) => (p.kind === 'text' ? p.text : '')).join('')
  return (
    <div className="flex justify-end motion-safe:animate-msg-in">
      <p className="max-w-[85%] rounded-2xl rounded-br-md bg-navy-50 px-3.5 py-2 text-[15px] leading-relaxed whitespace-pre-wrap text-navy-900">
        {text}
      </p>
    </div>
  )
}

type ToolPart = Extract<MessagePart, { kind: 'tool' }>
type Block = { kind: 'text'; text: string } | { kind: 'steps'; tools: ToolPart[] }

/** Consecutive tool calls become one block between the pieces of text. */
function toBlocks(parts: MessagePart[]): Block[] {
  const blocks: Block[] = []
  for (const part of parts) {
    const last = blocks.at(-1)
    if (part.kind === 'text') blocks.push({ kind: 'text', text: part.text })
    else if (last?.kind === 'steps') last.tools.push(part)
    else blocks.push({ kind: 'steps', tools: [part] })
  }
  return blocks
}

function AssistantMessage({
  message,
  onShowTimeline,
}: {
  message: ChatMessage
  onShowTimeline: Props['onShowTimeline']
}) {
  const lastPart = message.parts.at(-1)
  const status =
    message.status !== 'streaming' || lastPart?.kind === 'text'
      ? null
      : !lastPart
        ? 'Myślę…'
        : lastPart.status === 'running'
          ? 'Sprawdzam…'
          : 'Piszę odpowiedź…'

  return (
    <div className="flex flex-col items-start gap-3 motion-safe:animate-msg-in">
      {toBlocks(message.parts).map((block, index) =>
        block.kind === 'text' ? (
          <TextBlock key={index} text={block.text} />
        ) : (
          <ChangeCard key={index} tools={block.tools} onShowTimeline={onShowTimeline} />
        ),
      )}
      {status && (
        <span className="flex items-center gap-2 text-sm text-navy-500">
          <span className="size-1.5 rounded-full bg-zus-400 motion-safe:animate-pulse" />
          <TextStates text={status} />
        </span>
      )}
      {message.error && (
        <p className="rounded-2xl bg-alert-50 px-3 py-2 text-sm text-alert-600">{message.error}</p>
      )}
    </div>
  )
}

function TextBlock({ text }: { text: string }) {
  const { text: clean, sources } = splitCitations(text)
  return (
    <div className="w-full text-[15px] leading-relaxed text-navy-700">
      <Markdown components={MARKDOWN}>{clean}</Markdown>
      {sources.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {sources.map((source) => (
            <span
              key={source}
              className="rounded-full bg-navy-50 px-2.5 py-0.5 text-xs font-bold text-navy-500"
            >
              {source}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/** What the assistant changed (or showed) on the timeline, with a way back to it. */
function ChangeCard({
  tools,
  onShowTimeline,
}: {
  tools: ToolPart[]
  onShowTimeline: Props['onShowTimeline']
}) {
  const running = tools.some((t) => t.status === 'running')
  const failed = tools.filter((t) => t.status === 'failed')
  const changes = tools.filter((t) => PLAN_TOOLS.has(t.name) && t.status === 'done')
  const shown = tools.find(
    (t) => t.name === 'explain_timeline_element' && typeof t.args.element_id === 'string',
  )
  const target = shown && typeof shown.args.element_id === 'string' ? shown.args.element_id : null
  const title = running
    ? 'Aktualizuję oś…'
    : changes.length > 0
      ? 'Oś zaktualizowana'
      : failed.length > 0
        ? 'Nie udało się zmienić osi'
        : 'Pokazuję na osi'

  return (
    <div
      className={cn(
        'w-full rounded-2xl border px-4 py-3',
        failed.length > 0 && !running ? 'border-alert-50 bg-alert-50/60' : 'border-line bg-white',
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'size-2 rounded-full',
            running
              ? 'bg-zus-400 motion-safe:animate-pulse'
              : failed.length > 0 && changes.length === 0
                ? 'bg-alert-600'
                : 'bg-zus-600',
          )}
        />
        <p className="flex-1 text-sm font-bold text-navy-900">
          <TextStates text={title} />
        </p>
        {!running && (changes.length > 0 || target) && (
          <button
            type="button"
            onClick={() => onShowTimeline(target)}
            className="group flex items-center gap-0.5 text-sm font-bold text-zus-700"
          >
            Pokaż
            <ChevronRight className="size-4 transition-transform duration-150 group-hover:translate-x-0.5" />
          </button>
        )}
      </div>
      {(changes.length > 0 || failed.length > 0) && (
        <ul className="mt-1.5 space-y-0.5 pl-4">
          {[...changes, ...failed].map((tool) => (
            <li
              key={tool.id}
              className={cn('text-sm', tool.status === 'failed' ? 'text-alert-600' : 'text-navy-700')}
            >
              {toolLabel(tool.name, tool.args)}
              {tool.status === 'failed' && ' — odrzucone'}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
