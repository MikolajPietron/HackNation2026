// Where parents can find support in hard situations (the brief, point i; FUNKCJE F28): charities
// and public services for the loss of a child, a premature baby, a seriously ill child, and an
// emotional crisis. Checked on the web on 22.11.2026. A link is given only where the address
// was confirmed; the rest name the organisation and what it does, without guessing a website.
import { ICONS } from './icons'

export type SupportTopic = 'loss' | 'premature' | 'ill' | 'crisis'

export interface SupportEntry {
  name: string
  what: string
  where?: string
  link?: { label: string; href: string }
}

export interface SupportGroup {
  topic: SupportTopic
  title: string
  icon: string
  entries: SupportEntry[]
}

export const CHECKED_ON = '2026-11-22'

export const SUPPORT: SupportGroup[] = [
  {
    topic: 'loss',
    title: 'Po stracie dziecka',
    icon: ICONS.serce,
    entries: [
      {
        name: 'Fundacja Rodzić po Ludzku',
        what: 'Informator „Poronienie i urodzenie martwego dziecka w szpitalu” (2025): prawa rodziców i co dzieje się w szpitalu.',
        link: {
          label: 'Informator (PDF)',
          href: 'https://gdzierodzic.info/wp-content/uploads/2025/09/Informator-Rodzic-po-Ludzku-Poronienie-i-urodzenie-martwego-dziecka-w-szpitalu-wersja-na-telefon-2025.pdf',
        },
      },
      {
        name: 'Stowarzyszenie Rodziców po Poronieniu',
        what: 'Rodzice, którzy wspierają rodziców po poronieniu.',
        where: 'Warszawa · KRS 0000260223',
      },
      {
        name: 'Ministerstwo Rodziny, Pracy i Polityki Społecznej',
        what: 'Prawa rodziców, którzy stracili dziecko.',
        link: { label: 'gov.pl', href: 'https://www.gov.pl/web/rodzina/wazne-zmiany-dla-rodzicow-ktorzy-stracili-dziecko' },
      },
    ],
  },
  {
    topic: 'premature',
    title: 'Wcześniak',
    icon: ICONS.inkubator,
    entries: [
      {
        name: 'Fundacja Wcześniak Rodzice-Rodzicom',
        what: 'Wiedza dla rodziców wcześniaków, bezpłatna wypożyczalnia sprzętu (np. monitory oddechu), poradnik „Niezbędnik rodzica wcześniaka”.',
        where: 'Warszawa · wczesniak@wczesniak.pl',
        link: { label: 'wczesniak.pl', href: 'https://www.wczesniak.pl' },
      },
    ],
  },
  {
    topic: 'ill',
    title: 'Ciężko chore dziecko',
    icon: ICONS.szpital,
    entries: [
      {
        name: 'Warszawskie Hospicjum Perinatalne',
        what: 'Opieka i wsparcie psychologiczne dla rodziców, gdy w ciąży rozpoznano ciężką wadę dziecka. Prowadzi Fundacja Warszawskie Hospicjum dla Dzieci.',
        where: 'Warszawa, ul. Agatowa 10',
      },
      {
        name: 'Fundacja Gajusz',
        what: 'Hospicjum perinatalne, stacjonarne i domowe dla dzieci.',
        where: 'Łódź',
      },
      {
        name: 'Narodowy Fundusz Zdrowia',
        what: 'Perinatalna opieka paliatywna finansowana przez NFZ.',
        link: {
          label: 'nfz.gov.pl',
          href: 'https://www.nfz.gov.pl/aktualnosci/aktualnosci-centrali/komunikat-dotyczacy-perinatalnej-opieki-paliatywnej,7857.html',
        },
      },
    ],
  },
  {
    topic: 'crisis',
    title: 'Kiedy jest bardzo ciężko',
    icon: ICONS.telefon,
    entries: [
      {
        name: 'Telefon 116 123',
        what: 'Dla dorosłych w kryzysie emocjonalnym: bezpłatnie i anonimowo, także czat. Prowadzi Niebieska Linia Instytutu Psychologii Zdrowia.',
        link: { label: '116sos.pl', href: 'https://116sos.pl' },
      },
      {
        name: 'Numer alarmowy 112',
        what: 'Gdy zagrożone jest życie lub zdrowie.',
      },
    ],
  },
]
