import { cn } from '@/lib/utils'

/**
 * One fading ring around something the last recalculation changed; remount it (`key`) to play
 * it again. Its parent is `relative`. A CSS animation on purpose: Motion skips mount animations
 * inside `AnimatePresence initial={false}` (the "Twoja sytuacja" list), and the ring must play.
 */
export function Pulse({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        'pointer-events-none absolute inset-0 animate-ring rounded-full opacity-0 ring-4 ring-sun-400 motion-reduce:animate-ring-still',
        className,
      )}
    />
  )
}
