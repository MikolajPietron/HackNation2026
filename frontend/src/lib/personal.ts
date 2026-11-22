// Personal data for the requests, typed once (FUNKCJE: "dane osobowe wpisane raz"). It stays in
// this browser only (localStorage): never sent to the server, never to AI. The request forms of
// the engine leave personal fields empty (`FormField.personal`); this fills them by field id.
import { useCallback, useSyncExternalStore } from 'react'
import type { FormField, RequestForm, Role } from '@/types'

export interface PersonData {
  name: string
  pesel: string
  address: string
  /** Bank account for the benefit (ZAM). */
  account: string
}

export interface EmployerData {
  name: string
  address: string
  nip: string
}

export interface Profile {
  /** The town in the "miejscowość, data" line. */
  place: string
  mother: PersonData
  father: PersonData
  motherEmployer: EmployerData
  fatherEmployer: EmployerData
  child: { name: string; pesel: string; birthPlace: string }
}

const KEY = 'zpr-profile-v1'
const EVENT = 'zpr-profile'

const person = (): PersonData => ({ name: '', pesel: '', address: '', account: '' })
const employer = (): EmployerData => ({ name: '', address: '', nip: '' })

export const EMPTY_PROFILE: Profile = {
  place: '',
  mother: person(),
  father: person(),
  motherEmployer: employer(),
  fatherEmployer: employer(),
  child: { name: '', pesel: '', birthPlace: '' },
}

let cached: { raw: string | null; profile: Profile } | null = null

function read(): Profile {
  let raw: string | null = null
  try {
    raw = window.localStorage.getItem(KEY)
  } catch {
    raw = null
  }
  if (cached && cached.raw === raw) return cached.profile
  let profile = EMPTY_PROFILE
  if (raw) {
    try {
      const stored = JSON.parse(raw) as Partial<Profile>
      profile = {
        ...EMPTY_PROFILE,
        ...stored,
        mother: { ...person(), ...stored.mother },
        father: { ...person(), ...stored.father },
        motherEmployer: { ...employer(), ...stored.motherEmployer },
        fatherEmployer: { ...employer(), ...stored.fatherEmployer },
        child: { ...EMPTY_PROFILE.child, ...stored.child },
      }
    } catch {
      profile = EMPTY_PROFILE
    }
  }
  cached = { raw, profile }
  return profile
}

export function saveProfile(profile: Profile) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(profile))
  } catch {
    // Private mode or storage off: the data lives until the page is closed.
    cached = { raw: JSON.stringify(profile), profile }
  }
  window.dispatchEvent(new Event(EVENT))
}

export function clearProfile() {
  try {
    window.localStorage.removeItem(KEY)
  } catch {
    // nothing stored
  }
  cached = null
  window.dispatchEvent(new Event(EVENT))
}

function subscribe(callback: () => void) {
  const onStorage = (event: StorageEvent) => event.key === KEY && callback()
  window.addEventListener(EVENT, callback)
  window.addEventListener('storage', onStorage)
  return () => {
    window.removeEventListener(EVENT, callback)
    window.removeEventListener('storage', onStorage)
  }
}

/** The saved profile, live across components and tabs. */
export function useProfile(): [Profile, (profile: Profile) => void] {
  const profile = useSyncExternalStore(subscribe, read, () => EMPTY_PROFILE)
  const save = useCallback((next: Profile) => saveProfile(next), [])
  return [profile, save]
}

/** How many of the main fields are filled in, for "Twoje dane: 4 z 6". */
export function profileProgress(profile: Profile, applicants: Role[]): { filled: number; total: number } {
  const values = [profile.place, profile.child.name]
  for (const role of applicants) {
    const p = role === 'mother' ? profile.mother : profile.father
    const e = role === 'mother' ? profile.motherEmployer : profile.fatherEmployer
    values.push(p.name, p.address, e.name)
  }
  return { filled: values.filter((v) => v.trim()).length, total: values.length }
}

/** The personal value for a form field, from the profile; '' when the profile has none. */
export function personalValue(field: FormField, form: RequestForm, profile: Profile): string {
  const me = form.applicant === 'father' ? profile.father : profile.mother
  const job = form.applicant === 'father' ? profile.fatherEmployer : profile.motherEmployer
  const id = field.id
  if (id === 'child-name') return profile.child.name
  if (id === 'child-pesel') return profile.child.pesel
  if (id === 'child-birth-place') return profile.child.birthPlace
  if (id === 'father-name') return profile.father.name
  if (id === 'mother-name') return profile.mother.name
  if (id.endsWith('-pesel')) return me.pesel
  if (id.endsWith('-address')) return me.address
  if (id === 'bank-account') return me.account
  if (id === 'payer-name' || id === 'employer-name') return job.name
  if (id === 'payer-nip' || id === 'employer-nip') return job.nip
  if (id === 'employer-address') return job.address
  if (id.endsWith('-name') && id !== 'payer-name') return me.name
  return ''
}

/** The applicant's own details for the letter's header. */
export function applicantOf(form: RequestForm, profile: Profile) {
  const me = form.applicant === 'father' ? profile.father : profile.mother
  const job = form.applicant === 'father' ? profile.fatherEmployer : profile.motherEmployer
  return { me, job }
}

/**
 * "Wypełnij z mObywatela" — a SIMULATION (the brief: only simulate the login): the test account's
 * made-up name and address. PESEL is never invented: the parent types it.
 */
export function fromMObywatel(profile: Profile, name: string, employerName: string, role: Role): Profile {
  const sample = { address: 'ul. Przykładowa 1/2, 00-001 Warszawa' }
  if (role === 'father') {
    return {
      ...profile,
      place: profile.place || 'Warszawa',
      father: { ...profile.father, name, address: profile.father.address || sample.address },
      fatherEmployer: { ...profile.fatherEmployer, name: profile.fatherEmployer.name || employerName },
    }
  }
  return {
    ...profile,
    place: profile.place || 'Warszawa',
    mother: { ...profile.mother, name, address: profile.mother.address || sample.address },
    motherEmployer: { ...profile.motherEmployer, name: profile.motherEmployer.name || employerName },
  }
}

/** The profile with a personal field's new value, so typing it in one request fills the rest. */
export function withPersonalValue(profile: Profile, field: FormField, form: RequestForm, value: string): Profile {
  const role = form.applicant === 'father' ? 'father' : 'mother'
  const meKey = role
  const jobKey = role === 'father' ? 'fatherEmployer' : 'motherEmployer'
  const me = profile[meKey]
  const job = profile[jobKey]
  const id = field.id
  if (id === 'child-name') return { ...profile, child: { ...profile.child, name: value } }
  if (id === 'child-pesel') return { ...profile, child: { ...profile.child, pesel: value } }
  if (id === 'child-birth-place') return { ...profile, child: { ...profile.child, birthPlace: value } }
  if (id === 'father-name') return { ...profile, father: { ...profile.father, name: value } }
  if (id === 'mother-name') return { ...profile, mother: { ...profile.mother, name: value } }
  if (id.endsWith('-pesel')) return { ...profile, [meKey]: { ...me, pesel: value } }
  if (id.endsWith('-address')) return { ...profile, [meKey]: { ...me, address: value } }
  if (id === 'bank-account') return { ...profile, [meKey]: { ...me, account: value } }
  if (id === 'payer-name' || id === 'employer-name') return { ...profile, [jobKey]: { ...job, name: value } }
  if (id === 'payer-nip' || id === 'employer-nip') return { ...profile, [jobKey]: { ...job, nip: value } }
  if (id === 'employer-address') return { ...profile, [jobKey]: { ...job, address: value } }
  if (id.endsWith('-name')) return { ...profile, [meKey]: { ...me, name: value } }
  return profile
}
