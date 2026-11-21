import { useEffect, useRef } from 'react'
import Markdown from 'react-markdown'
import type { Components } from 'react-markdown'
import { AgentSteps } from '@/components/ui/agent-steps'
import type { AgentStep } from '@/components/ui/agent-steps'
import { ChatEmptyState } from '@/components/ui/chat-empty-state'
import { PromptComposer } from '@/components/ui/prompt-composer'
import { TextStates } from '@/components/ui/text-states'
import type { ChatMessage, MessagePart } from '@/hooks/useAssistant'
import { toolLabel } from '@/lib/ui'

const SUGGESTIONS = [
  'Podam przewidywaną datę porodu',
  'Czy mogę iść na urlop przed porodem?',
  'Chcę pracować do dnia porodu',
]

const MARKDOWN: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  strong: ({ children }) => <strong className="font-black text-navy-900">{children}</strong>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-zus-700 underline">
      {children}
    </a>
  ),
}

interface Props {
  messages: ChatMessage[]
  busy: boolean
  /** The stored conversation is still loading: do not greet yet. */
  restoring: boolean
  onSend: (text: string) => void
  onStop: () => void
  /** Jump to the timeline (on phones it is a separate tab), optionally to one element. */
  onShowTimeline: (elementId: string | null) => void
}

export function ChatPanel({ messages, busy, restoring, onSend, onStop, onShowTimeline }: Props) {
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 px-5 pt-4 pb-1">
        <p className="font-black text-navy-900">Asystent</p>
        <span className="rounded-full bg-zus-600 px-2 py-0.5 text-[10px] font-black tracking-wide text-white">
          AI
        </span>
        <p className="ml-auto text-[11px] text-navy-500">Daty liczy kalkulator, nie AI</p>
      </div>

      <div ref={listRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-3" aria-live="polite">
        {restoring && messages.length === 0 ? null : messages.length === 0 ? (
          <ChatEmptyState
            title="Cześć! Przygotujmy się do porodu."
            subtitle={
              <>
                Na początek:{' '}
                <strong className="font-black text-navy-900">
                  jaka jest przewidywana data porodu?
                </strong>{' '}
                Podaj dzień, miesiąc i rok.
              </>
            }
            prompts={SUGGESTIONS}
            onSelectPrompt={onSend}
          />
        ) : (
          messages.map((message) =>
            message.role === 'user' ? (
              <UserMessage key={message.id} message={message} />
            ) : (
              <AssistantMessage key={message.id} message={message} onShowTimeline={onShowTimeline} />
            ),
          )
        )}
      </div>

      <div className="px-3 pb-3">
        <PromptComposer onSend={onSend} onStop={onStop} isGenerating={busy} />
        <p className="mt-2 px-3 text-[11px] leading-snug text-navy-500">
          Nie podawaj danych osobowych. AI może się mylić — źródła są przy elementach osi.
        </p>
      </div>
    </div>
  )
}

function UserMessage({ message }: { message: ChatMessage }) {
  const text = message.parts.map((p) => (p.kind === 'text' ? p.text : '')).join('')
  return (
    <div className="flex justify-end motion-safe:animate-msg-in">
      <p className="max-w-[85%] rounded-3xl rounded-br-lg bg-zus-600 px-4 py-2.5 text-[15px] whitespace-pre-wrap text-white">
        {text}
      </p>
    </div>
  )
}

type ToolPart = Extract<MessagePart, { kind: 'tool' }>
type Block = { kind: 'text'; text: string } | { kind: 'steps'; tools: ToolPart[] }

/** Consecutive tool calls become one list of steps between the pieces of text. */
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

  const toStep = (tool: ToolPart): AgentStep => {
    const linkable = tool.status === 'done'
    const target =
      tool.name === 'explain_timeline_element' && typeof tool.args.element_id === 'string'
        ? tool.args.element_id
        : null
    return {
      id: tool.id,
      label: toolLabel(tool.name, tool.args),
      status: tool.status === 'running' ? 'running' : tool.status === 'done' ? 'success' : 'error',
      hint: 'pokaż',
      hintClassName: 'lg:hidden',
      onClick: linkable ? () => onShowTimeline(target) : undefined,
    }
  }

  return (
    <div className="flex flex-col items-start gap-2.5 motion-safe:animate-msg-in">
      {toBlocks(message.parts).map((block, index) =>
        block.kind === 'text' ? (
          <div key={index} className="text-[15px] leading-relaxed text-navy-700">
            <Markdown components={MARKDOWN}>{block.text}</Markdown>
          </div>
        ) : (
          <AgentSteps key={index} steps={block.tools.map(toStep)} />
        ),
      )}
      {status && (
        <span className="flex items-center gap-2 text-sm text-navy-500">
          <span className="size-2 rounded-full bg-zus-400 motion-safe:animate-pulse" />
          <TextStates text={status} />
        </span>
      )}
      {message.error && (
        <p className="rounded-2xl bg-alert-50 px-3 py-2 text-sm text-alert-600">{message.error}</p>
      )}
    </div>
  )
}
