// "Kopiuj" next to a date or an amount: one tap and it is ready to paste into a form on zus.pl
// or an e-mail to HR. A tick confirms it, and screen readers hear it.
import { useEffect, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'


export function CopyValue({
  value,
  label,
  className,
}: {
  /** What goes to the clipboard, e.g. "02.08.2027" or "5 626,11 zł". */
  value: string
  /** What is copied, for the button's name: "datę", "kwotę". */
  label?: string
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const timer = useRef(0)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  return (
    <button
      type="button"
      onClick={async (event) => {
        event.stopPropagation()
        if (await copyText(value)) {
          setCopied(true)
          window.clearTimeout(timer.current)
          timer.current = window.setTimeout(() => setCopied(false), 1400)
        }
      }}
      title={copied ? 'Skopiowano' : `Kopiuj ${label ?? ''}`.trim()}
      aria-label={copied ? `Skopiowano: ${value}` : `Kopiuj ${label ?? value}`}
      className={cn(
        'inline-flex size-7 shrink-0 items-center justify-center rounded-full text-navy-400 transition-[background-color,color,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-90 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        copied && 'text-zus-600 hover:text-zus-600',
        className,
      )}
    >
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      <span role="status" className="sr-only">
        {copied ? 'Skopiowano' : ''}
      </span>
    </button>
  )
}
