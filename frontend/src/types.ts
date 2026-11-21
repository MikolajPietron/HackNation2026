// Mirrors backend/app/engine/models.py and the /api/chat event protocol. Keep in sync.
// Phase 1: guide section A, "Przygotowanie do porodu" (page 5).

export type Lane = 'mother' | 'child' | 'documents'
/** leave = leave the mother takes, work = she keeps working, option = possible, not decided. */
export type Tone = 'leave' | 'work' | 'option'

export interface SourceRef {
  doc: 'przewodnik'
  section: string
  page: number
  quote: string
}

export interface Scenario {
  due_date: string | null
  leave_before_birth_weeks: number | null
  has_medical_certificate: boolean | null
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

export interface Timeline {
  params_version: string
  today: string
  due_date: string
  segments: Segment[]
  markers: Marker[]
  documents: Document[]
  warnings: string[]
  assumptions: string[]
}

export interface ChatRequest {
  session_id: string
  message: string
}

/** A stored conversation, as returned by GET /api/session/{id}. */
export interface SessionView {
  messages: StoredMessage[]
  timeline: Timeline | null
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
      focus: string | null
    }
  | { type: 'focus'; element_id: string }
  | { type: 'done' }
  | { type: 'error'; message: string }
