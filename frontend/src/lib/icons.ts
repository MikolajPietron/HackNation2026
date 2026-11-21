// Which illustration stands for which element, so the timeline, the summary, the playhead
// readout and the dialogs speak one picture language. By the engine's ids first, then by
// keywords for elements the engine adds in later phases.
import aktUrodzenia from '@/assets/onboarding/akt-urodzenia.webp'
import blizniaki from '@/assets/onboarding/blizniaki.webp'
import dom from '@/assets/onboarding/dom.webp'
import etat from '@/assets/onboarding/etat.webp'
import inkubator from '@/assets/onboarding/inkubator.webp'
import kalendarz from '@/assets/onboarding/kalendarz.webp'
import karton from '@/assets/onboarding/karton.webp'
import klepsydra from '@/assets/onboarding/klepsydra.webp'
import koperta from '@/assets/onboarding/koperta.webp'
import mamaZDzieckiem from '@/assets/onboarding/mama-z-dzieckiem.webp'
import noworodek from '@/assets/onboarding/noworodek.webp'
import odpoczynek from '@/assets/onboarding/odpoczynek.webp'
import parasol from '@/assets/onboarding/parasol.webp'
import pieniadze from '@/assets/onboarding/pieniadze.webp'
import serce from '@/assets/onboarding/serce.webp'
import skarbonka from '@/assets/onboarding/skarbonka.webp'
import szpital from '@/assets/onboarding/szpital.webp'
import tataZDzieckiem from '@/assets/onboarding/tata-z-dzieckiem.webp'
import telefon from '@/assets/onboarding/telefon.webp'
import trojaczki from '@/assets/onboarding/trojaczki.webp'
import waga from '@/assets/onboarding/waga.webp'
import wozek from '@/assets/onboarding/wozek.webp'
import zaswiadczenie from '@/assets/onboarding/zaswiadczenie.webp'
import zlecenie from '@/assets/onboarding/zlecenie.webp'
import type { Document, Marker, Segment } from '../types'

export const ICONS = {
  aktUrodzenia,
  blizniaki,
  dom,
  etat,
  inkubator,
  kalendarz,
  karton,
  klepsydra,
  koperta,
  mamaZDzieckiem,
  noworodek,
  odpoczynek,
  parasol,
  pieniadze,
  serce,
  skarbonka,
  szpital,
  tataZDzieckiem,
  telefon,
  trojaczki,
  waga,
  wozek,
  zaswiadczenie,
  zlecenie,
}

export function segmentIcon(segment: Segment): string {
  const id = segment.id
  if (segment.tone === 'work' || id.startsWith('work')) return etat
  if (id === 'prenatal-window' || id === 'maternity-prenatal') return odpoczynek
  if (id.includes('paternity')) return tataZDzieckiem
  if (id.includes('parental')) return wozek
  if (id.includes('supplementary') || id.includes('premature')) return inkubator
  return mamaZDzieckiem
}

export function markerIcon(marker: Marker): string {
  if (marker.id === 'birth' || marker.id === 'due-date' || marker.id === 'taken-in') return noworodek
  if (marker.id === 'personal-weeks' || marker.id.includes('window') || marker.id.includes('deadline')) {
    return klepsydra
  }
  return kalendarz
}

export function documentIcon(document: Document): string {
  if (document.id.includes('certificate')) return zaswiadczenie
  if (document.id.includes('birth')) return aktUrodzenia
  return koperta
}

/**
 * Key days are events (the birth, deadlines, windows that close); the rest are hints (the end
 * of the weeks only the mother can take, the earliest possible start).
 */
export function isKeyMarker(marker: Marker): boolean {
  return (
    marker.id === 'birth' ||
    marker.id === 'due-date' ||
    marker.id === 'taken-in' ||
    marker.id.includes('deadline') ||
    marker.id.includes('window') ||
    marker.id.includes('limit')
  )
}
