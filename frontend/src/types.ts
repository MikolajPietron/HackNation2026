// Mirrors backend/app/engine/models.py and the /api/chat event protocol. Keep in sync.
// Phases 1-3: guide section A, "Przygotowanie do porodu", "Urodzenie dziecka" and the stillbirth
// or death of the child (pages 5-6).

export type Lane = 'mother' | 'child' | 'documents'
/** leave = leave the mother takes, work = she keeps working, option = possible, not decided. */
export type Tone = 'leave' | 'work' | 'option'

export type Role = 'mother' | 'father'
export type Work = 'employment' | 'contract' | 'business' | 'none'
export type Earnings = 'under-5k' | '5k-8k' | '8k-12k' | 'over-12k' | 'unknown'
/** When the child was born, as the Labour Code art. 180² § 1 divides it (weeks of pregnancy). */
export type BirthWeek = 'before-28' | '28-37' | 'after-37'

/** A literal quote: from the guide (section and pages) or from the Labour Code (article). */
export interface SourceRef {
  doc: 'przewodnik' | 'kp'
  quote: string
  section: string | null
  page: number | null
  /** Set when the quote runs over a page break. */
  page_to: number | null
  article: string | null
}

/** A child of this birth who was stillborn (no date) or died on `died_on`. */
export interface ChildLoss {
  stillborn: boolean
  died_on: string | null
}

/** One stay of the child in hospital after the birth; no `end` = still there. */
export interface HospitalStay {
  start: string
  end: string | null
}

/** What the onboarding and the interview have established. null = not known yet. */
export interface Scenario {
  /** The person filling in. Work and earnings are that person's own. */
  role: Role | null
  work: Work | null
  earnings: Earnings | null
  /** How the mother works, when somebody else fills in. */
  mother_work: Work | null
  child_born: boolean | null
  due_date: string | null
  birth_date: string | null
  children_count: number | null
  leave_before_birth_weeks: number | null
  has_medical_certificate: boolean | null
  /** Voluntary sickness insurance of a mother on a contract or with her own business. */
  mother_insured: boolean | null
  za_zyciem: boolean | null
  /** Born child: premature, or in hospital after the birth. */
  hospital_care: boolean | null
  birth_week: BirthWeek | null
  birth_weight_up_to_1000g: boolean | null
  hospital_stays: HospitalStay[]
  /** Recorded only when the parent says so. */
  losses: ChildLoss[]
}

/** Everything the onboarding asks, as sent to PUT /api/session/{id}/onboarding. */
export interface OnboardingAnswers {
  role: Role
  child_born: boolean
  /** Date of birth when `child_born`, otherwise the expected due date. */
  date: string
  children_count: number
  work: Work
  earnings: Earnings | null
}

export interface Segment {
  id: string
  lane: Lane
  tone: Tone
  title: string
  start: string
  end: string
  days: number
  summary: string
  details: string[]
  sources: SourceRef[]
}

export interface Marker {
  id: string
  lane: Lane
  label: string
  title: string
  date: string
  summary: string
  details: string[]
  sources: SourceRef[]
}

export interface Document {
  id: string
  label: string
  title: string
  needed_by: string
  done: boolean
  rule: string
  segment_id: string | null
  sources: SourceRef[]
}

/**
 * One point of the case explanation: situation = which case this is, right = what the mother is
 * entitled to, risk = what stands in the way of an entitlement, choice = what the family can
 * decide, relief = an easier or longer path the rules give them, computed = what we calculated.
 */
export interface CaseNote {
  id: string
  kind: 'situation' | 'right' | 'risk' | 'choice' | 'relief' | 'computed'
  title: string
  text: string
  sources: SourceRef[]
}

export interface Timeline {
  params_version: string
  today: string
  /** Actual date of birth when `child_born`, otherwise the expected due date. */
  birth_date: string
  child_born: boolean
  children_count: number | null
  segments: Segment[]
  markers: Marker[]
  documents: Document[]
  notes: CaseNote[]
  warnings: string[]
  assumptions: string[]
}

/** An app event the assistant reacts to instead of a message; the user does not see it. */
export type AppEvent = 'timeline_ready'

/** A user message or an app event, one of the two. */
export interface ChatRequest {
  session_id: string
  message?: string
  event?: AppEvent
}

/** A stored conversation, as returned by GET /api/session/{id}. */
export interface SessionView {
  messages: StoredMessage[]
  scenario: Scenario
  timeline: Timeline | null
}

/** The onboarding answers as stored, and the first timeline. */
export interface SessionStart {
  scenario: Scenario
  timeline: Timeline
}

export type StoredPart =
  | { kind: 'text'; text: string }
  | {
      kind: 'tool'
      id: string
      name: string
      args: Record<string, unknown>
      status: 'running' | 'done' | 'failed'
    }

export interface StoredMessage {
  id: string
  role: 'user' | 'assistant'
  parts: StoredPart[]
  status: 'streaming' | 'done'
}

export type ChatEvent =
  | { type: 'text'; delta: string }
  | { type: 'tool-call'; id: string; name: string; args: Record<string, unknown> }
  | { type: 'tool-result'; id: string; name: string; ok: boolean }
  | {
      type: 'timeline'
      scenario: Scenario
      timeline: Timeline | null
      changed: string[]
      changed_notes: string[]
      focus: string | null
    }
  | { type: 'focus'; element_id: string }
  | { type: 'done' }
  | { type: 'error'; message: string }
