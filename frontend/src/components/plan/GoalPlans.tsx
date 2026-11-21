// "Plany dla Was" — plans from what the family cares about (FUNKCJE F8, F12). The decision tree
// that proposes them is being built; until then the cards show the shape of each plan and say
// that applying it is not wired yet.
import { motion } from 'motion/react'
import { SimBadge } from '@/components/mocks/MockModal'
import { ITEM } from '@/components/onboarding/motion'
import { SPRING_PRESS } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { GOAL_PLANS } from '@/lib/mockData'

const PLAN_ICON: Record<string, string> = {
  money: ICONS.skarbonka,
  home: ICONS.dom,
  equal: ICONS.waga,
}

export function GoalPlans({ onMock }: { onMock: (message: string) => void }) {
  return (
    <motion.section variants={ITEM} className="mt-12" aria-label="Plany dla Was">
      <div className="flex items-end gap-4">
        <div className="flex-1">
          <h2 className="text-2xl leading-tight font-bold tracking-tight text-navy-900">Plany dla Was</h2>
          <p className="mt-1 text-navy-500">Na czym Wam zależy? Wybierz plan, a ułożymy go na osi.</p>
        </div>
        <SimBadge>przykład</SimBadge>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-4">
        {GOAL_PLANS.map((plan) => (
          <div key={plan.id} className="flex flex-col rounded-3xl border border-line p-5">
            <img src={PLAN_ICON[plan.id]} alt="" draggable={false} className="mb-3 size-16 object-contain" />
            <h3 className="text-lg font-bold text-navy-900">{plan.title}</h3>
            <p className="mt-1 flex-1 text-sm leading-relaxed text-navy-500">{plan.summary}</p>
            <div className="mt-4 space-y-1.5">
              <Track who="Mama" bars={plan.mother} className="bg-zus-600" />
              <Track who="Tata" bars={plan.father} className="bg-navy-700" />
            </div>
            <div className="mt-4 flex gap-2">
              <motion.button
                type="button"
                onClick={() => onMock(`Plan „${plan.title}” ułoży drzewo decyzyjne — w przygotowaniu.`)}
                whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
                className="h-9 flex-1 rounded-full bg-zus-600 text-sm font-bold text-white transition-colors duration-200 hover:bg-zus-700"
              >
                Zastosuj
              </motion.button>
              <motion.button
                type="button"
                onClick={() => onMock('Porównanie planów obok siebie — w przygotowaniu.')}
                whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
                className="h-9 rounded-full border border-line px-4 text-sm font-bold text-navy-900 transition-colors duration-200 hover:bg-navy-50"
              >
                Porównaj
              </motion.button>
            </div>
          </div>
        ))}
      </div>
    </motion.section>
  )
}

function Track({ who, bars, className }: { who: string; bars: [number, number][]; className: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-9 text-xs font-bold text-navy-500">{who}</span>
      <div className="relative h-2.5 flex-1 rounded-full bg-navy-50">
        {bars.map(([start, end]) => (
          <span
            key={start}
            className={`absolute inset-y-0 rounded-full ${className}`}
            style={{ left: `${start * 100}%`, width: `${(end - start) * 100}%` }}
          />
        ))}
      </div>
    </div>
  )
}
