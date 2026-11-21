import { motion } from 'motion/react'
import { Baby, ChartGantt, Info, MessageCircle, RotateCcw } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { SPRING_LAYOUT } from '@/lib/ease'
import { cn } from '@/lib/utils'

export type Tab = 'chat' | 'timeline' | 'about'

const ITEMS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: 'chat', label: 'Rozmowa', icon: MessageCircle },
  { id: 'timeline', label: 'Oś czasu', icon: ChartGantt },
  { id: 'about', label: 'Założenia', icon: Info },
]

export function Logo({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'grid shrink-0 place-items-center rounded-full bg-zus-600 text-white shadow-pill',
        className,
      )}
    >
      <Baby className="size-[55%]" />
    </span>
  )
}

/** Desktop: narrow icon rail. The chat is always visible there, so it has no entry. */
export function Rail({
  tab,
  onChange,
  onReset,
  className,
}: {
  tab: Tab
  onChange: (tab: Tab) => void
  onReset: () => void
  className?: string
}) {
  const active = tab === 'about' ? 'about' : 'timeline'
  return (
    <nav
      aria-label="Widoki"
      className={cn(
        'w-[76px] shrink-0 flex-col items-center gap-2 border-r border-line bg-white py-5',
        className,
      )}
    >
      <Logo className="mb-6 size-11" />
      {ITEMS.filter((item) => item.id !== 'chat').map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          aria-label={label}
          aria-current={active === id ? 'page' : undefined}
          title={label}
          className={cn(
            'relative grid size-11 place-items-center rounded-2xl transition-colors',
            active === id ? 'text-zus-700' : 'text-navy-400 hover:text-navy-700',
          )}
        >
          {active === id && (
            <motion.span
              layoutId="rail-active"
              transition={SPRING_LAYOUT}
              className="absolute inset-0 rounded-2xl bg-zus-50"
            />
          )}
          <Icon className="relative size-5" />
        </button>
      ))}
      <button
        type="button"
        onClick={onReset}
        aria-label="Zacznij od nowa"
        title="Zacznij od nowa"
        className="mt-auto grid size-11 place-items-center rounded-2xl text-navy-400 transition-colors hover:bg-navy-50 hover:text-navy-700"
      >
        <RotateCcw className="size-5" />
      </button>
    </nav>
  )
}

/** Phones: bottom bar, one panel at a time. */
export function BottomNav({
  tab,
  onChange,
  timelineBadge,
  className,
}: {
  tab: Tab
  onChange: (tab: Tab) => void
  timelineBadge: boolean
  className?: string
}) {
  return (
    <nav
      aria-label="Widoki"
      className={cn('grid grid-cols-3 gap-1 border-t border-line bg-white p-1.5', className)}
    >
      {ITEMS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          aria-current={tab === id ? 'page' : undefined}
          className={cn(
            'relative flex flex-col items-center gap-0.5 rounded-2xl py-1.5 text-[11px] font-bold transition-colors',
            tab === id ? 'text-zus-700' : 'text-navy-500',
          )}
        >
          {tab === id && (
            <motion.span
              layoutId="bottom-nav-active"
              transition={SPRING_LAYOUT}
              className="absolute inset-0 rounded-2xl bg-zus-50"
            />
          )}
          <span className="relative">
            <Icon className="size-5" />
            {id === 'timeline' && timelineBadge && (
              <span
                className="absolute -top-0.5 -right-1.5 size-2 rounded-full bg-sun-400 ring-2 ring-white"
                aria-label="nowe zmiany"
              />
            )}
          </span>
          <span className="relative">{label}</span>
        </button>
      ))}
    </nav>
  )
}
