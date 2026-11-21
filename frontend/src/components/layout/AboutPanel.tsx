import type { ReactNode } from 'react'
import { formatLongDate } from '@/lib/dates'
import { childrenLabel } from '@/lib/ui'
import type { Earnings, Scenario, Timeline, Work } from '@/types'

/** What the calculator assumes, what is AI and what is not, and where the rules come from. */
const WORK: Record<Work, string> = {
  employment: 'na etacie (umowa o pracę)',
  contract: 'na umowie zlecenia',
  business: 'własna firma (JDG)',
  none: 'nie pracuje',
}

const EARNINGS: Record<Earnings, string> = {
  'under-5k': 'do 5 000 zł',
  '5k-8k': '5 000 – 8 000 zł',
  '8k-12k': '8 000 – 12 000 zł',
  'over-12k': 'powyżej 12 000 zł',
  unknown: 'nie wiem',
}

/** The answers that are known, as label/value rows. */
function answerRows(scenario: Scenario): [string, string][] {
  const date = scenario.child_born ? scenario.birth_date : scenario.due_date
  const rows: [string, string | null][] = [
    ['Kto wypełnia', scenario.role && (scenario.role === 'mother' ? 'mama' : 'tata')],
    ['Dziecko', scenario.child_born === null ? null : scenario.child_born ? 'już jest' : 'w drodze'],
    [scenario.child_born ? 'Data urodzenia' : 'Przewidywana data porodu', date && formatLongDate(date)],
    ['Liczba dzieci', scenario.children_count ? childrenLabel(scenario.children_count) : null],
    ['Praca', scenario.work && WORK[scenario.work]],
    ['Zarobki brutto', scenario.earnings && EARNINGS[scenario.earnings]],
  ]
  return rows.filter((row): row is [string, string] => Boolean(row[1]))
}

export function AboutPanel({
  scenario,
  timeline,
}: {
  scenario: Scenario | null
  timeline: Timeline | null
}) {
  const answers = scenario ? answerRows(scenario) : []
  return (
    <div className="mx-auto max-w-2xl space-y-5 p-5 lg:p-8">
      <h1 className="text-2xl font-black text-navy-900 lg:text-3xl">Założenia i źródła</h1>

      <Card title="Co robi AI, a co kalkulator">
        <p>
          Rozmowę prowadzi asystent AI. Daty na osi liczy kalkulator reguł — bez AI. Każdy element
          osi ma dosłowny cytat z Przewodnika ZUS albo Kodeksu pracy.
        </p>
      </Card>

      {answers.length > 0 && (
        <Card title="Twoje odpowiedzi">
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-sm">
            {answers.map(([label, value]) => (
              <div key={label} className="contents">
                <dt className="text-navy-500">{label}</dt>
                <dd className="font-bold text-navy-900">{value}</dd>
              </div>
            ))}
          </dl>
          {(scenario?.work || scenario?.earnings) && (
            <p className="mt-3 text-xs text-navy-500">
              Pracę i zarobki wykorzystamy w kolejnych etapach: kto wypłaca zasiłek, wnioski, kwoty.
            </p>
          )}
        </Card>
      )}

      <Card title="Założenia kalkulatora">
        {timeline ? (
          <ul className="list-disc space-y-1.5 pl-5 marker:text-zus-400">
            {timeline.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        ) : (
          <p>Pojawią się, gdy podasz przewidywaną datę porodu.</p>
        )}
      </Card>

      <Card title="Źródła">
        <ul className="list-disc space-y-1.5 pl-5 marker:text-zus-400">
          <li>
            Przewodnik ZUS z opisu wyzwania HackNation 2026, sekcja A „Zasiłek macierzyński dla
            kobiety” (s. 5): przygotowanie do porodu, wymiar urlopu macierzyńskiego, 14 tygodni po
            porodzie.
          </li>
          <li>Kodeks pracy: art. 180 § 1–3 i art. 183¹ § 1–2 (urlop macierzyński).</li>
        </ul>
        {timeline && (
          <p className="mt-3 text-xs text-navy-500">Wersja parametrów: {timeline.params_version}</p>
        )}
      </Card>

      <p className="px-1 text-xs text-navy-500">
        Wersja demonstracyjna. Nie zastępuje decyzji ZUS ani pracodawcy.
      </p>
    </div>
  )
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl bg-white p-6 text-[15px] leading-relaxed text-navy-700 shadow-card">
      <h2 className="mb-2 text-xs font-black tracking-widest text-zus-700 uppercase">{title}</h2>
      {children}
    </section>
  )
}
