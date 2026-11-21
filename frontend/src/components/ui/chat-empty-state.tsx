// Adapted from Spectrum UI (https://ui.spectrumhq.in, Apache-2.0): blocks/ai-assistants/chat-empty-state.
// Changes: our colour tokens, the title can hold emphasis, keyframes moved to index.css.

import type { ReactNode } from 'react'
import { Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ChatEmptyStateProps {
  title: string
  subtitle: ReactNode
  prompts?: string[]
  onSelectPrompt?: (prompt: string) => void
  className?: string
}

export function ChatEmptyState({
  title,
  subtitle,
  prompts = [],
  onSelectPrompt,
  className,
}: ChatEmptyStateProps) {
  return (
    <div className={cn('w-full', className)}>
      <div className="grid size-10 place-items-center rounded-2xl bg-zus-600 text-white">
        <Sparkles className="size-5" />
      </div>
      <h3 className="mt-4 text-lg font-black tracking-[-0.2px] text-navy-900">{title}</h3>
      <p className="mt-1.5 text-[15px] leading-[1.6] text-navy-700">{subtitle}</p>

      {prompts.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-1.5">
          {prompts.map((prompt, index) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onSelectPrompt?.(prompt)}
              style={{ animationDelay: `${Math.min(index, 5) * 50}ms` }}
              className={cn(
                'rounded-full border border-line bg-white px-3 py-1.5 text-left text-[13px] text-navy-700',
                'transition-[color,border-color,background-color,transform] duration-150 active:scale-[0.96]',
                'hover:border-zus-300 hover:bg-zus-50 hover:text-zus-900',
                'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-hidden',
                'motion-safe:animate-msg-in',
              )}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
