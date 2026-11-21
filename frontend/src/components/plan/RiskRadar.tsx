// "Na co uważać" — risks of losing or lowering the benefit (FUNKCJE F26, brief point h), picked
// by the form of work from the onboarding. Information from the guide (pp. 9–10), not a verdict:
// the engine will decide when it computes the right to the benefit.
import { motion } from 'motion/react'
import { ITEM } from '@/components/onboarding/motion'
import { ICONS } from '@/lib/icons'
import { cn } from '@/lib/utils'
import type { Scenario } from '@/types'

type Level = 'risk' | 'check' | 'ok' | 'info'

const LEVEL: Record<Level, { label: string; className: string }> = {
  risk: { label: 'Ryzyko', className: 'bg-alert-50 text-alert-600' },
  check: { label: 'Sprawdź', className: 'bg-sun-100 text-sun-700' },
  ok: { label: 'W porządku', className: 'bg-zus-50 text-zus-700' },
  info: { label: 'Dobrze wiedzieć', className: 'bg-navy-50 text-navy-500' },
}

const RISK_ICON: Record<string, string> = {
  insured: ICONS.parasol,
  sham: ICONS.zlecenie,
  debt: ICONS.pieniadze,
  raise: ICONS.skarbonka,
  continuity: ICONS.kalendarz,
  voluntary: ICONS.parasol,
}

interface Risk {
  id: string
  level: Level
  title: string
  text: string
  action?: { label: string; onClick: () => void }
}

function risks(scenario: Scenario | null, onCheckZus: () => void): Risk[] {
  const work = scenario?.work ?? null
  const own = work === 'contract' || work === 'business'
  const list: Risk[] = [
    {
      id: 'insured',
      level: work === 'employment' ? 'ok' : work === 'none' ? 'risk' : 'check',
      title: 'Ubezpieczenie chorobowe w dniu porodu',
      text:
        work === 'employment'
          ? 'Na etacie masz je z umowy. Uważaj, jeśli umowa kończy się przed porodem.'
          : work === 'none'
            ? 'Bez ubezpieczenia nie ma zasiłku macierzyńskiego. Zobacz, co przysługuje zamiast.'
            : 'Na zleceniu i w firmie chorobowe jest dobrowolne. Musi trwać w dniu porodu.',
    },
    {
      id: 'sham',
      level: 'info',
      title: 'Umowa albo firma „dla pozoru”',
      text: 'Umowę zawartą tylko po to, by dostać zasiłek, ZUS może zakwestionować.',
    },
  ]
  if (work === 'business') {
    list.push(
      {
        id: 'debt',
        level: 'check',
        title: 'Zaległe składki',
        text: 'Zadłużenie na dzień powstania prawa może wstrzymać zasiłek.',
        action: { label: 'Sprawdź w danych z ZUS', onClick: onCheckZus },
      },
      {
        id: 'raise',
        level: 'check',
        title: 'Podwyższenie podstawy składek w ciąży',
        text: 'Nagłe podniesienie podstawy tuż przed porodem ZUS może zakwestionować.',
      },
      {
        id: 'continuity',
        level: 'check',
        title: 'Chorobowe po macierzyńskim',
        text: 'Po macierzyńskim zgłoś się ponownie do dobrowolnego chorobowego. Przerwa przed rodzicielskim oznacza odmowę zasiłku.',
      },
    )
  } else if (own) {
    list.push({
      id: 'voluntary',
      level: 'check',
      title: 'Dobrowolne chorobowe na zleceniu',
      text: 'Zasiłek chorobowy w ciąży (L4) przysługuje po 90 dniach dobrowolnego ubezpieczenia. Sprawdź, od kiedy je masz.',
      action: { label: 'Sprawdź w danych z ZUS', onClick: onCheckZus },
    })
  }
  return list
}

export function RiskRadar({ scenario, onCheckZus }: { scenario: Scenario | null; onCheckZus: () => void }) {
  return (
    <motion.section variants={ITEM} className="mt-12" aria-label="Na co uważać">
      <h2 className="text-2xl leading-tight font-bold tracking-tight text-navy-900">Na co uważać</h2>
      <p className="mt-1 text-navy-500">Wstępnie, na podstawie Twoich odpowiedzi · Przewodnik ZUS, s. 9–10</p>
      <ul className="mt-5 divide-y divide-line rounded-3xl border border-line">
        {risks(scenario, onCheckZus).map((risk) => (
          <li key={risk.id} className="flex items-center gap-4 px-5 py-4">
            <img src={RISK_ICON[risk.id]} alt="" draggable={false} className="size-12 shrink-0 object-contain" />
            <span
              className={cn(
                'w-28 shrink-0 rounded-full px-2.5 py-1 text-center text-xs font-bold',
                LEVEL[risk.level].className,
              )}
            >
              {LEVEL[risk.level].label}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-bold text-navy-900">{risk.title}</p>
              <p className="mt-0.5 text-sm leading-relaxed text-navy-500">{risk.text}</p>
            </div>
            {risk.action && (
              <button
                type="button"
                onClick={risk.action.onClick}
                className="shrink-0 text-sm font-bold text-zus-700 underline-offset-2 hover:underline"
              >
                {risk.action.label}
              </button>
            )}
          </li>
        ))}
      </ul>
    </motion.section>
  )
}
