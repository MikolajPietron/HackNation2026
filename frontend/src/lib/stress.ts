// Words and pictures for the stress test's events (FUNKCJE F11), shared by the tiles, the chips
// and the preview banner. The verdicts and lines themselves are the engine's.
import { ICONS } from './icons'
import type { StressEventId, StressVerdict } from '../types'

export const STRESS_ICON: Record<StressEventId, string> = {
  premature: ICONS.inkubator,
  twins: ICONS.blizniaki,
  'job-loss-bankruptcy': ICONS.karton,
  'job-loss-liquidation': ICONS.karton,
  'job-loss-employer-death': ICONS.karton,
  'job-loss-unlawful': ICONS.karton,
  'job-loss-other': ICONS.karton,
  'mother-incapacity': ICONS.szpital,
  'mother-hospital': ICONS.szpital,
  'mother-death': ICONS.serce,
  'father-takeover': ICONS.tataZDzieckiem,
  'za-zyciem': ICONS.serce,
}

export const VERDICT: Record<StressVerdict, { label: string; chip: string; bar: string }> = {
  kept: { label: 'prawa zostają', chip: 'bg-zus-50 text-zus-700', bar: 'bg-zus-600' },
  risk: { label: 'ryzyko', chip: 'bg-sun-100 text-sun-700', bar: 'bg-sun-400' },
  loss: { label: 'coś przepada', chip: 'bg-sun-100 text-sun-700 ring-1 ring-sun-300', bar: 'bg-sun-700' },
}

/** What the assistant is told when the event really happened; it then asks for the details. */
export const HAPPENED: Partial<Record<StressEventId, string>> = {
  premature: 'Dziecko urodziło się przedwcześnie i jest w szpitalu',
  twins: 'Spodziewamy się bliźniąt',
  'job-loss-bankruptcy': 'Mama straciła pracę w ciąży: pracodawca ogłosił upadłość',
  'job-loss-liquidation': 'Mama straciła pracę w ciąży: pracodawca jest likwidowany',
  'job-loss-employer-death': 'Mama straciła pracę w ciąży: pracodawca zmarł',
  'job-loss-unlawful': 'Pracodawca rozwiązał z mamą umowę w ciąży z naruszeniem przepisów',
  'job-loss-other': 'Praca mamy skończyła się w ciąży',
  'father-takeover': 'Tata przejmie urlop macierzyński po 14 tygodniach',
  'za-zyciem': 'Dziecko ma zaświadczenie „Za życiem”',
}

export const REASON: Partial<Record<StressEventId, string>> = {
  'job-loss-bankruptcy': 'upadłość',
  'job-loss-liquidation': 'likwidacja',
  'job-loss-employer-death': 'śmierć pracodawcy',
  'job-loss-unlawful': 'bezprawne zwolnienie',
  'job-loss-other': 'inny powód',
}
