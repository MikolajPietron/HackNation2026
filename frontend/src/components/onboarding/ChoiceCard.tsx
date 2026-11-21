// Choice controls of the onboarding. Radio pattern and press feedback after Spectrum UI's
// model-selector (role="radio", border states, active scale, dot that scales in).
//
// Motion owns opacity/transform/filter of the cards (entrance, press). Hover lift and dimming
// run in CSS on inner elements, so the two never fight over the same property.
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Check } from 'lucide-react'
import { SPRING_PRESS, SPRING_SWAP } from '@/lib/ease'
import { cn } from '@/lib/utils'
import { ITEM } from './motion'

interface ChoiceProps {
  label: string
  hint?: string
  selected: boolean
  /** Another option was just chosen and the step is about to leave. */
  dimmed?: boolean
  onSelect: () => void
}

const CARD = cn(
  'outline-none focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2',
  'transition-[border-color,background-color,box-shadow] duration-200',
)

/** A large card with an illustration. */
export function ImageChoice({ image, label, hint, selected, dimmed, onSelect }: ChoiceProps & { image: string }) {
  return (
    <motion.button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      variants={ITEM}
      whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
      className={cn(
        CARD,
        'group relative flex flex-col items-center rounded-4xl border bg-white px-4 pt-6 pb-5 sm:px-6 sm:pt-8 sm:pb-7',
        selected
          ? 'border-zus-600 bg-zus-50 shadow-[0_0_0_1px_var(--color-zus-600)]'
          : 'border-line hover:border-navy-200 hover:shadow-card',
      )}
    >
      <span
        className={cn(
          'flex w-full flex-col items-center transition-opacity duration-200',
          dimmed && 'opacity-35',
        )}
      >
        <img
          src={image}
          alt=""
          draggable={false}
          className="aspect-square max-h-[34vh] w-full object-contain transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] select-none group-hover:-translate-y-1.5"
        />
        <span className="mt-4 text-lg leading-tight font-bold text-navy-900 sm:text-xl">{label}</span>
        {hint && <span className="mt-1 text-sm text-navy-500 sm:text-base">{hint}</span>}
      </span>
      <AnimatePresence>
        {selected && (
          <motion.span
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={SPRING_SWAP}
            className="absolute top-4 right-4 grid size-8 place-items-center rounded-full bg-zus-600 text-white"
          >
            <Check className="size-4" strokeWidth={3} />
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  )
}

/** A full-width row for answers without a picture. */
export function TextChoice({ label, hint, selected, dimmed, onSelect }: ChoiceProps) {
  return (
    <motion.button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      variants={ITEM}
      whileTap={{ scale: 0.985, transition: SPRING_PRESS }}
      className={cn(
        CARD,
        'flex w-full rounded-2xl border bg-white px-6 py-5 text-left',
        selected
          ? 'border-zus-600 bg-zus-50 shadow-[0_0_0_1px_var(--color-zus-600)]'
          : 'border-line hover:border-navy-200 hover:shadow-card',
      )}
    >
      <span
        className={cn(
          'flex w-full items-center gap-4 transition-opacity duration-200',
          dimmed && 'opacity-35',
        )}
      >
        <span className="min-w-0 flex-1">
          <span className="block text-lg font-bold text-navy-900">{label}</span>
          {hint && <span className="block text-sm text-navy-500">{hint}</span>}
        </span>
        <span
          aria-hidden
          className={cn(
            'grid size-5 shrink-0 place-items-center rounded-full border-2 transition-colors duration-150',
            selected ? 'border-zus-600' : 'border-navy-200',
          )}
        >
          <span
            className={cn(
              'size-2.5 rounded-full bg-zus-600 transition-transform duration-200 ease-[cubic-bezier(0.23,1,0.32,1)]',
              selected ? 'scale-100' : 'scale-0',
            )}
          />
        </span>
      </span>
    </motion.button>
  )
}

/** The main action of a step. */
export function PrimaryButton({
  children,
  disabled,
  type = 'button',
  onClick,
  className,
}: {
  children: ReactNode
  disabled?: boolean
  type?: 'button' | 'submit'
  onClick?: () => void
  className?: string
}) {
  return (
    <motion.button
      type={type}
      disabled={disabled}
      onClick={onClick}
      whileTap={disabled ? undefined : { scale: 0.97, transition: SPRING_PRESS }}
      className={cn(
        'inline-flex h-14 items-center justify-center gap-2 rounded-full bg-zus-600 px-8 text-lg font-bold text-white',
        'transition-[background-color,opacity] duration-200 hover:bg-zus-700',
        'outline-none focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2',
        'disabled:pointer-events-none disabled:opacity-30',
        className,
      )}
    >
      {children}
    </motion.button>
  )
}
