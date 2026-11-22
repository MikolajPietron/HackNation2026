// Our mark: mama, the baby and tata from the illustration set, side by side like on the first
// screen. Not the ZUS logo (CLAUDE.md: we only borrow the palette).
import dziecko from '@/assets/onboarding/dziecko.webp'
import mama from '@/assets/onboarding/mama.webp'
import tata from '@/assets/onboarding/tata.webp'
import { cn } from '@/lib/utils'

const SIZES = {
  sm: { parent: 'h-9 w-5', baby: 'h-6 w-6 -mx-0.5' },
  md: { parent: 'h-12 w-7', baby: 'h-8 w-8 -mx-1' },
}

/** The family mark alone. Narrow figures are cropped to their own width. */
export function BrandMark({ size = 'md', className }: { size?: keyof typeof SIZES; className?: string }) {
  const s = SIZES[size]
  return (
    <span className={cn('flex shrink-0 items-end', className)} aria-hidden>
      <img src={mama} alt="" draggable={false} className={cn('object-cover select-none', s.parent)} />
      <img
        src={dziecko}
        alt=""
        draggable={false}
        className={cn('relative z-10 object-contain select-none', s.baby)}
      />
      <img src={tata} alt="" draggable={false} className={cn('object-cover select-none', s.parent)} />
    </span>
  )
}

/** The mark with the product name in two lines. */
export function Brand({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-center gap-3', className)}>
      <BrandMark />
      <span className="text-[15px] leading-tight font-bold tracking-tight whitespace-nowrap">
        <span className="block text-navy-900">Zasiłkowy Przewodnik</span>
        <span className="block text-zus-700">Przyszłego Rodzica</span>
      </span>
    </span>
  )
}
