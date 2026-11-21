import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import type { Components } from 'react-markdown'
import type { ChatMessage, MessagePart } from '../../hooks/useAssistant'
import { cx, TIMELINE_TOOLS, toolLabel } from '../../lib/ui'
import { CheckIcon, SendIcon, SparklesIcon, SpinnerIcon, XIcon } from '../Icons'

const SUGGESTIONS = [
  'Jestem w ciąży, podam termin porodu',
  'Dziecko już się urodziło',
  'Spodziewamy się bliźniąt',
  'Czym różni się urlop macierzyński od rodzicielskiego?',
]

const MARKDOWN: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  strong: ({ children }) => <strong className="font-semibold text-stone-950">{children}</strong>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-teal-700 underline">
      {children}
    </a>
  ),
}

interface Props {
  messages: ChatMessage[]
  busy: boolean
  onSend: (text: string) => void
  /** Jump to the timeline (on phones it is a separate tab), optionally to one element. */
  onShowTimeline: (elementId: string | null) => void
}

export function ChatPanel({ messages, busy, onSend, onShowTimeline }: Props) {
  const [draft, setDraft] = useState('')
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const started = messages.some((m) => m.role === 'user')

  useEffect(() => {
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages])

  useEffect(() => {
    const input = inputRef.current
    if (!input) return
    input.style.height = 'auto'
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`
  }, [draft])

  const submit = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    onSend(trimmed)
    setDraft('')
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-3 border-b border-stone-200 px-4 py-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-teal-600 text-white">
          <SparklesIcon className="size-5" />
        </span>
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-semibold text-stone-900">
            Asystent
            <span className="rounded-full bg-teal-50 px-2 py-0.5 text-[11px] font-semibold text-teal-700 ring-1 ring-teal-200">
              AI
            </span>
          </p>
          <p className="text-xs text-stone-500">
            Rozmowę prowadzi model AI. Daty liczy kalkulator reguł, nie AI.
          </p>
        </div>
      </div>

      <div ref={listRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-5" aria-live="polite">
        {messages.map((message) =>
          message.role === 'user' ? (
            <UserMessage key={message.id} message={message} />
          ) : (
            <AssistantMessage key={message.id} message={message} onShowTimeline={onShowTimeline} />
          ),
        )}
        {!started && (
          <div className="flex flex-wrap gap-2 pt-1">
            {SUGGESTIONS.map((text) => (
              <button
                key={text}
                type="button"
                onClick={() => submit(text)}
                className="rounded-full bg-white px-3 py-1.5 text-left text-sm text-stone-700 ring-1 ring-stone-300 transition hover:bg-teal-50 hover:ring-teal-300"
              >
                {text}
              </button>
            ))}
          </div>
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault()
          submit(draft)
        }}
        className="border-t border-stone-200 bg-white p-3"
      >
        <div className="flex items-end gap-2 rounded-2xl border border-stone-300 bg-white p-1.5 focus-within:border-teal-600 focus-within:ring-2 focus-within:ring-teal-600/20">
          <textarea
            ref={inputRef}
            value={draft}
            rows={1}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                submit(draft)
              }
            }}
            placeholder="Napisz wiadomość…"
            aria-label="Wiadomość do asystenta"
            className="flex-1 resize-none bg-transparent px-2.5 py-2 text-[15px] text-stone-900 outline-none placeholder:text-stone-400"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            aria-label="Wyślij"
            className="grid size-10 shrink-0 place-items-center rounded-xl bg-teal-600 text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? <SpinnerIcon className="size-5" /> : <SendIcon className="size-5" />}
          </button>
        </div>
        <p className="mt-2 px-1 text-[11px] leading-snug text-stone-500">
          Nie podawaj danych osobowych. Asystent może się mylić — przy każdym elemencie osi masz
          źródło z cytatem.
        </p>
      </form>
    </div>
  )
}

function UserMessage({ message }: { message: ChatMessage }) {
  const text = message.parts.map((p) => (p.kind === 'text' ? p.text : '')).join('')
  return (
    <div className="flex justify-end motion-safe:animate-rise">
      <p className="max-w-[85%] rounded-2xl rounded-br-md bg-stone-900 px-4 py-2.5 text-[15px] whitespace-pre-wrap text-white">
        {text}
      </p>
    </div>
  )
}

function AssistantMessage({
  message,
  onShowTimeline,
}: {
  message: ChatMessage
  onShowTimeline: Props['onShowTimeline']
}) {
  const waiting = message.status === 'streaming' && message.parts.length === 0
  return (
    <div className="flex max-w-[94%] flex-col items-start gap-2 motion-safe:animate-rise">
      {message.parts.map((part, index) =>
        part.kind === 'text' ? (
          <div
            key={index}
            className="rounded-2xl rounded-bl-md bg-white px-4 py-3 text-[15px] leading-relaxed text-stone-800 shadow-sm ring-1 ring-stone-200"
          >
            <Markdown components={MARKDOWN}>{part.text}</Markdown>
          </div>
        ) : (
          <ToolChip key={part.id} part={part} onShowTimeline={onShowTimeline} />
        ),
      )}
      {waiting && (
        <span className="flex items-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm text-stone-500 ring-1 ring-stone-200">
          <SpinnerIcon /> Myślę…
        </span>
      )}
      {message.error && (
        <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-800 ring-1 ring-red-200">
          {message.error}
        </p>
      )}
    </div>
  )
}

function ToolChip({
  part,
  onShowTimeline,
}: {
  part: Extract<MessagePart, { kind: 'tool' }>
  onShowTimeline: Props['onShowTimeline']
}) {
  const icon =
    part.status === 'running' ? (
      <SpinnerIcon className="size-3.5" />
    ) : part.status === 'done' ? (
      <CheckIcon className="size-3.5 text-teal-600" />
    ) : (
      <XIcon className="size-3.5 text-red-600" />
    )
  const linkable = part.status === 'done' && TIMELINE_TOOLS.has(part.name)
  const target =
    part.name === 'explain_timeline_element' && typeof part.args.element_id === 'string'
      ? part.args.element_id
      : null
  const className = cx(
    'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1',
    part.status === 'failed'
      ? 'bg-red-50 text-red-800 ring-red-200'
      : 'bg-stone-100 text-stone-700 ring-stone-200',
  )
  const content = (
    <>
      {icon}
      <span>{toolLabel(part.name, part.args)}</span>
      {part.status === 'failed' && <span className="text-red-700">· odrzucone</span>}
    </>
  )
  if (!linkable) return <span className={className}>{content}</span>
  return (
    <button
      type="button"
      onClick={() => onShowTimeline(target)}
      className={cx(className, 'transition hover:bg-teal-50 hover:ring-teal-300')}
    >
      {content}
      <span className="text-teal-700 lg:hidden">· pokaż</span>
    </button>
  )
}
