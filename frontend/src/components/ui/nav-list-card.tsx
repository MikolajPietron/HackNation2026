// Adapted from Spectrum UI (https://ui.spectrumhq.in, Apache-2.0): nav-list-card.
// Changes: our colour tokens, a second line (meta) and a trailing chevron per row, rows are
// buttons with a selected state, demo items removed.

import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface NavListItem {
  id: string
  icon: ReactNode
  /** Classes of the rounded icon tile (background and text colour). */
  iconClassName: string
  label: string
  meta: string
  metaClassName?: string
  selected?: boolean
  onSelect: () => void
}

export function NavListCard({
  title,
  items,
  className,
}: {
  title: string
  items: NavListItem[]
  className?: string
}) {
  return (
    <div className={cn('w-full', className)}>
      <p className="px-1 text-xs font-bold tracking-wide text-navy-500 uppercase">{title}</p>
      <ul className="mt-2 space-y-1">
        {items.map((item) => (
          <li key={item.id}>
            <button type="button" onClick={item.onSelect} className="block w-full text-left">
              <motion.span
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.98 }}
                transition={{ type: 'spring', bounce: 0.4, duration: 0.3 }}
                className={cn(
                  'flex items-center gap-3 rounded-2xl p-1.5 pr-2 transition-colors',
                  item.selected ? 'bg-zus-50' : 'hover:bg-navy-50',
                )}
              >
                <span
                  className={cn(
                    'grid size-9 shrink-0 place-items-center rounded-xl [&_svg]:size-4',
                    item.iconClassName,
                  )}
                >
                  {item.icon}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm leading-5 font-bold text-navy-900">
                    {item.label}
                  </span>
                  <span className={cn('block truncate text-xs text-navy-500', item.metaClassName)}>
                    {item.meta}
                  </span>
                </span>
                <ChevronRight className="size-4 shrink-0 text-zus-600" />
              </motion.span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
