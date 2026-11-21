// Adapted from Spectrum UI (https://ui.spectrumhq.in, Apache-2.0): blocks/ai-assistants/prompt-composer,
// "Minimal" variant. Changes: our colour tokens, Polish labels, no attachments or model picker,
// a leading badge (the AI label the challenge requires) and an optional voice button.

import { useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { ArrowUp, Mic, Square } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface PromptComposerProps {
  placeholder?: string
  onSend: (text: string) => void
  onStop?: () => void
  isGenerating?: boolean
  maxLength?: number
  /** Shown before the text field, e.g. an "AI" label. */
  badge?: ReactNode
  /** Voice input; the button is shown only when this is set. */
  onVoice?: () => void
  className?: string
}

const MAX_HEIGHT_PX = 144

export function PromptComposer({
  placeholder = 'Napisz wiadomość…',
  onSend,
  onStop,
  isGenerating = false,
  maxLength = 2000,
  badge,
  onVoice,
  className,
}: PromptComposerProps) {
  const [value, setValue] = useState('')
  const textarea = useRef<HTMLTextAreaElement>(null)
  const canSend = value.trim().length > 0 && !isGenerating

  function submit() {
    if (!canSend) return
    onSend(value.trim())
    setValue('')
    if (textarea.current) textarea.current.style.height = 'auto'
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
      className={cn(
        'flex items-end gap-2 rounded-[26px] border border-line bg-white py-1.5 pr-1.5 pl-2',
        'transition-[border-color,box-shadow] duration-200 focus-within:border-zus-400 focus-within:ring-4 focus-within:ring-zus-600/10',
        className,
      )}
    >
      {badge && <span className="mb-2 shrink-0 self-end">{badge}</span>}
      <textarea
        ref={textarea}
        value={value}
        rows={1}
        maxLength={maxLength}
        placeholder={placeholder}
        aria-label="Wiadomość do asystenta"
        onChange={(event) => {
          setValue(event.target.value)
          event.target.style.height = 'auto'
          event.target.style.height = `${Math.min(event.target.scrollHeight, MAX_HEIGHT_PX)}px`
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            submit()
          }
        }}
        className="min-w-0 flex-1 resize-none bg-transparent py-2 text-[15px] leading-6 text-navy-900 outline-none placeholder:text-navy-400"
      />
      {onVoice && (
        <button
          type="button"
          onClick={onVoice}
          aria-label="Mów zamiast pisać"
          title="Mów zamiast pisać"
          className="grid size-10 shrink-0 place-items-center rounded-full text-navy-400 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.92]"
        >
          <Mic className="size-[18px]" />
        </button>
      )}
      <button
        type={isGenerating ? 'button' : 'submit'}
        onClick={isGenerating ? onStop : undefined}
        aria-label={isGenerating ? 'Zatrzymaj odpowiedź' : 'Wyślij'}
        disabled={!isGenerating && !canSend}
        className="grid size-10 shrink-0 place-items-center rounded-full bg-zus-600 text-white transition-[transform,opacity,background-color] duration-[160ms] ease-[cubic-bezier(0.23,1,0.32,1)] hover:bg-zus-700 active:scale-[0.92] disabled:opacity-30"
      >
        <span className="relative grid size-4 place-items-center">
          <ArrowUp
            className={cn(
              'absolute size-4 transition-[opacity,filter] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)]',
              isGenerating ? 'opacity-0 blur-[2px]' : 'blur-0 opacity-100',
            )}
          />
          <Square
            className={cn(
              'absolute size-3 fill-current transition-[opacity,filter] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)]',
              isGenerating ? 'blur-0 opacity-100' : 'opacity-0 blur-[2px]',
            )}
          />
        </span>
      </button>
    </form>
  )
}
