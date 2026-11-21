// The three sizes our illustrations come in, so every icon of one kind is the same size:
// - event: what matters on the plan (periods, key days, documents to get) — 32 px on a 36 px tile,
// - hint: supporting information (informational days, readout lines, chips) — 24 px, no tile,
// - lane: who or what a timeline track is about — 56 px, no tile.
// Tall figures and wide objects sit in the same square, so their boxes line up.
import { cn } from '@/lib/utils'

export type IllustrationSize = 'event' | 'hint' | 'lane'

export function Illustration({
  src,
  size,
  className,
}: {
  src: string
  size: IllustrationSize
  className?: string
}) {
  const image = (
    <img
      src={src}
      alt=""
      draggable={false}
      className={cn(
        'shrink-0 object-contain select-none',
        size === 'event' ? 'size-8' : size === 'hint' ? 'size-6' : 'size-14',
        size !== 'event' && className,
      )}
    />
  )
  if (size !== 'event') return image
  return (
    <span className={cn('grid size-9 shrink-0 place-items-center rounded-lg bg-white', className)}>{image}</span>
  )
}
