// Format checks for the personal data in the requests: PESEL, NIP, the bank account (NRB) and the
// dates written on the paper. They run in this browser only, so the data never leaves it (the
// request check on the server gets only "(wpisane)"). Each returns a short message in plain
// Polish, or null when the value is fine. Empty is fine: whether a field is needed at all is
// the request check's job, not the format's.

/** Only the digits of what was typed. */
export const digits = (value: string) => value.replace(/\D/g, '')

/** Separators people type inside numbers: spaces and dashes. */
const compact = (value: string) => value.replace(/[\s-]/g, '')

const length = (name: string, expected: number, got: number) =>
  got < expected
    ? `${name} ma ${expected} cyfr — brakuje ${expected - got}.`
    : `${name} ma ${expected} cyfr — tu jest ${got}.`

const TYPO = 'Sprawdź, czy nie ma literówki.'

const PESEL_WEIGHTS = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]

/** The month code of a PESEL: 1–12 for 1900–1999, +20 for 2000s, +40, +60, +80 for 1800s. */
function peselBirthDate(pesel: string): boolean {
  const year = Number(pesel.slice(0, 2))
  const code = Number(pesel.slice(2, 4))
  const day = Number(pesel.slice(4, 6))
  const centuries: Record<number, number> = { 0: 1900, 20: 2000, 40: 2100, 60: 2200, 80: 1800 }
  const offset = Math.floor((code - 1) / 20) * 20
  const month = code - offset
  const century = centuries[offset]
  if (century === undefined || month < 1 || month > 12) return false
  return validDay(century + year, month, day)
}

/**
 * PESEL: 11 digits with the official check digit (weights 1-3-7-9) and a real date of birth.
 * `passport`: the field also takes a passport number when there is no PESEL (ZAM, ZAS-53), so a
 * value with letters is left alone.
 */
export function peselError(value: string, { passport = false } = {}): string | null {
  const v = compact(value)
  if (!v) return null
  if (/\D/.test(v)) return passport ? null : 'PESEL to same cyfry.'
  if (v.length !== 11) return length('PESEL', 11, v.length)
  const sum = PESEL_WEIGHTS.reduce((total, weight, i) => total + weight * Number(v[i]), 0)
  if ((10 - (sum % 10)) % 10 !== Number(v[10])) return `Ten PESEL ma błędną cyfrę kontrolną. ${TYPO}`
  if (!peselBirthDate(v)) return `W tym PESEL-u nie ma prawdziwej daty urodzenia. ${TYPO}`
  return null
}

const NIP_WEIGHTS = [6, 5, 7, 2, 3, 4, 5, 6, 7]

/**
 * NIP: 10 digits (dashes and a "PL" prefix are fine), the check digit is the weighted sum mod 11
 * (10 never is one). `withRegon`: the ZUS forms ask for "NIP i REGON" in one box, so a value that
 * has more than the NIP in it is left alone.
 */
export function nipError(value: string, { withRegon = false } = {}): string | null {
  const v = compact(value).replace(/^pl/i, '')
  if (!v) return null
  if (/\D/.test(v)) return withRegon ? null : 'NIP to same cyfry.'
  if (withRegon && v.length > 10) return null
  if (v.length !== 10) return length('NIP', 10, v.length)
  const sum = NIP_WEIGHTS.reduce((total, weight, i) => total + weight * Number(v[i]), 0)
  const check = sum % 11
  if (check === 10 || check !== Number(v[9])) return `Ten NIP ma błędną cyfrę kontrolną. ${TYPO}`
  return null
}

/** The IBAN check of a Polish account: "PL" + the 26 digits, moved and read mod 97, gives 1. */
function ibanOk(account: string): boolean {
  // P = 25, L = 21; the country code and the 2 check digits go to the end.
  const moved = `${account.slice(2)}2521${account.slice(0, 2)}`
  let rest = 0
  for (const digit of moved) rest = (rest * 10 + Number(digit)) % 97
  return rest === 1
}

/** A Polish bank account (NRB): 26 digits, spaces fine, may start with "PL". */
export function accountError(value: string): string | null {
  const v = compact(value).replace(/^pl/i, '')
  if (!v) return null
  if (/\D/.test(v)) return 'Numer konta to same cyfry (może zaczynać się od PL).'
  if (v.length !== 26) return length('Numer konta', 26, v.length)
  if (!ibanOk(v)) return `Ten numer konta ma błędne cyfry kontrolne. ${TYPO}`
  return null
}

/** The account as banks write it, while typing: "PL" if typed, then 2 + 6 groups of 4 digits. */
export function formatAccount(value: string): string {
  const prefix = (value.trimStart().match(/^pl?/i)?.[0] ?? '').toUpperCase()
  const d = digits(value).slice(0, 26)
  const groups = [d.slice(0, 2), ...(d.slice(2).match(/.{1,4}/g) ?? [])].filter(Boolean)
  return `${prefix}${groups.join(' ')}`
}

/** PESEL as it is typed: digits only, at most 11. */
export const peselDigits = (value: string) => digits(value).slice(0, 11)

/**
 * Where the caret goes after a value is reformatted: right after the same number of characters
 * (spaces not counted) as before it.
 */
export function caretAfter(formatted: string, kept: number): number {
  if (kept <= 0) return 0
  let seen = 0
  for (let i = 0; i < formatted.length; i++) {
    if (formatted[i] !== ' ') seen++
    if (seen === kept) return i + 1
  }
  return formatted.length
}

/**
 * What an input with a format passes on: the typed value reformatted (digits only, the account
 * in groups), with the caret kept after the same character when typing in the middle.
 */
export function typed(input: HTMLInputElement, format: ((value: string) => string) | undefined): string {
  if (!format) return input.value
  const caret = input.selectionStart ?? input.value.length
  const next = format(input.value)
  if (caret < input.value.length) {
    const at = caretAfter(next, input.value.slice(0, caret).replace(/\s/g, '').length)
    // After React writes the new value (which puts the caret at the end).
    requestAnimationFrame(() => input.setSelectionRange(at, at))
  }
  return next
}

function validDay(year: number, month: number, day: number): boolean {
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

const MONTHS = [
  'stycznia',
  'lutego',
  'marca',
  'kwietnia',
  'maja',
  'czerwca',
  'lipca',
  'sierpnia',
  'września',
  'października',
  'listopada',
  'grudnia',
]

/**
 * A date on the request: 05.03.2027 (also with / or -), 2027-03-05 or "5 marca 2027 r." — what the
 * request check on the server reads (documents/dates.py). Anything else it would skip silently.
 */
export function dateError(value: string): string | null {
  const v = value.trim().replace(/\s*r\.?$/i, '')
  if (!v) return null
  let parts: [number, number, number] | null = null
  const dayFirst = v.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/)
  const iso = v.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
  const words = v.toLowerCase().match(/^(\d{1,2})\s+(\p{L}+)\s+(\d{4})$/u)
  if (dayFirst) parts = [Number(dayFirst[3]), Number(dayFirst[2]), Number(dayFirst[1])]
  else if (iso) parts = [Number(iso[1]), Number(iso[2]), Number(iso[3])]
  else if (words && MONTHS.includes(words[2])) parts = [Number(words[3]), MONTHS.indexOf(words[2]) + 1, Number(words[1])]
  if (!parts) return 'Wpisz datę jako DD.MM.RRRR, np. 05.03.2027.'
  if (!validDay(...parts)) return 'Taki dzień nie istnieje — sprawdź dzień i miesiąc.'
  return null
}
