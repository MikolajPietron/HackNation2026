import type { ReactNode } from 'react'
import { formatLongDate } from '@/lib/dates'
import { childrenLabel, WORK_LABEL } from '@/lib/ui'
import type { BirthWeek, Earnings, MotherEvent, Scenario, Timeline } from '@/types'

/** What the calculator assumes, what is AI and what is not, and where the rules come from. */
const BIRTH_WEEK: Record<BirthWeek, string> = {
  'before-28': 'przed ukończeniem 28. tygodnia ciąży',
  '28-37': 'po 28. i przed ukończeniem 37. tygodnia ciąży',
  'after-37': 'po ukończeniu 37. tygodnia ciąży',
}

const EARNINGS: Record<Earnings, string> = {
  'under-5k': 'do 5 000 zł',
  '5k-8k': '5 000 – 8 000 zł',
  '8k-12k': '8 000 – 12 000 zł',
  'over-12k': 'powyżej 12 000 zł',
  unknown: 'nie wiem',
}

const yesNo = (value: boolean | null, yes: string, no: string) =>
  value === null ? null : value ? yes : no

/** The mother's special situation (guide section B), in plain and quiet words. */
function motherEventText(event: MotherEvent): string {
  const start = formatLongDate(event.start)
  switch (event.kind) {
    case 'hospital':
      return event.end
        ? `pobyt w szpitalu od ${start} do ${formatLongDate(event.end)}`
        : `pobyt w szpitalu od ${start}, nadal trwa`
    case 'incapacity':
      return `orzeczenie o niezdolności do samodzielnej egzystencji; tata przejmuje urlop od ${start}`
    case 'abandonment':
      return `porzucenie dziecka ${start}`
    case 'death':
      return `zmarła ${start}`
  }
}

/** The answers that are known, as label/value rows. */
function answerRows(scenario: Scenario): [string, string][] {
  const date = scenario.child_born ? scenario.birth_date : scenario.due_date
  // Each parent's work comes from their own answer when they fill in, else from what was said.
  const rows: [string, string | null][] = [
    ['Kto wypełnia', scenario.role && (scenario.role === 'mother' ? 'mama' : 'tata')],
    ['Dziecko', scenario.child_born === null ? null : scenario.child_born ? 'już jest' : 'w drodze'],
    [scenario.child_born ? 'Data urodzenia' : 'Przewidywana data porodu', date && formatLongDate(date)],
    ['Liczba dzieci', scenario.children_count ? childrenLabel(scenario.children_count) : null],
    [
      scenario.role === 'father' ? 'Praca taty' : 'Praca mamy',
      scenario.work && WORK_LABEL[scenario.work],
    ],
    ['Zarobki brutto', scenario.earnings && EARNINGS[scenario.earnings]],
    [
      'Praca mamy',
      scenario.role !== 'mother' && scenario.mother_work ? WORK_LABEL[scenario.mother_work] : null,
    ],
    ['Dobrowolne ubezpieczenie chorobowe mamy', yesNo(scenario.mother_insured, 'jest', 'brak')],
    [
      'Praca taty',
      scenario.role !== 'father' && scenario.father_work ? WORK_LABEL[scenario.father_work] : null,
    ],
    ['Dobrowolne ubezpieczenie chorobowe taty', yesNo(scenario.father_insured, 'jest', 'brak')],
    [
      'Tata przejmuje urlop macierzyński',
      yesNo(
        scenario.father_takes_over,
        scenario.mother_weeks_before_takeover
          ? `tak, po ${scenario.mother_weeks_before_takeover} tyg. urlopu mamy`
          : 'tak',
        'nie',
      ),
    ],
    ['Sytuacja mamy', scenario.mother_event && motherEventText(scenario.mother_event)],
    ['Zaświadczenie „Za życiem”', scenario.za_zyciem ? 'jest' : null],
    [
      'Wcześniak albo szpital po porodzie',
      scenario.hospital_care === null ? null : scenario.hospital_care ? 'tak' : 'nie',
    ],
    ['Dziecko urodziło się', scenario.birth_week && BIRTH_WEEK[scenario.birth_week]],
    [
      'Masa urodzeniowa',
      scenario.birth_weight_up_to_1000g === null
        ? null
        : scenario.birth_weight_up_to_1000g
          ? 'nie więcej niż 1000 g'
          : 'więcej niż 1000 g',
    ],
    [
      'Dzieci, które zmarły',
      scenario.losses
        .map((loss) => (loss.stillborn ? 'urodziło się martwe' : `zmarło ${formatLongDate(loss.died_on ?? '')}`))
        .join('; ') || null,
    ],
    [
      'Pobyt dziecka w szpitalu',
      scenario.hospital_stays
        .map((stay) => `${formatLongDate(stay.start)} – ${stay.end ? formatLongDate(stay.end) : 'nadal'}`)
        .join('; ') || null,
    ],
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
          {scenario?.earnings && (
            <p className="mt-3 text-xs text-navy-500">
              Zarobki wykorzystamy w kolejnym etapie, przy kwotach zasiłku.
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
            kobiety” (s. 5–6), punkty „Przygotowanie do porodu” i „Urodzenie dziecka”, oraz
            fragmenty, na których te punkty się opierają: ubezpieczenie chorobowe (s. 3–5 i 10),
            uzupełniający urlop macierzyński (s. 8).
          </li>
          <li>
            Przewodnik ZUS, sekcja B „Zasiłek macierzyński dla mężczyzny (ojca dziecka)” (s. 7–8):
            przejęcie urlopu macierzyńskiego przez tatę, także w sytuacjach szczególnych, urlop
            rodzicielski obojga rodziców i urlop ojcowski.
          </li>
          <li>
            Kodeks pracy: art. 180 i 183¹ (urlop macierzyński), art. 180 § 4–14 (przejęcie urlopu
            macierzyńskiego przez ojca), art. 180² (uzupełniający urlop macierzyński), art. 182¹ᵃ,
            182¹ᶜ i 182¹ᵍ (urlop rodzicielski), art. 182³ (urlop ojcowski).
          </li>
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
