// Mirrors backend/app/engine/models.py and the /api/chat event protocol. Keep in sync.

export type Lane = 'mother' | 'father' | 'child' | 'applications'
export type Parent = 'mother' | 'father'
export type DocId = 'przewodnik' | 'kp' | 'ustawa'

export interface SourceRef {
  doc: DocId
  page: number | null
  article: string | null
  quote: string | null
}

export interface Scenario {
  birth_date: string | null
  child_born: boolean
  children_count: number
  maternity_weeks_before_birth: number
  flat_rate: boolean
  paternity_start: string | null
}

export interface Segment {
  id: string
  lane: Lane
  title: string
  start: string
  end: string
  days: number
  rate_percent: number
  benefit: string
  payer: string
  summary: string
  details: string[]
  is_example: boolean
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

export interface Application {
  id: string
  parent: Parent
  label: string
  title: string
  due: string
  is_deadline: boolean
  rule: string
  where: string
  segment_id: string | null
  passed: boolean
  sources: SourceRef[]
}

export interface Stat {
  id: string
  label: string
  value: number
  unit: string
  lane: Lane
  segment_ids: string[]
}

export interface Timeline {
  params_version: string
  today: string
  birth_date: string
  child_born: boolean
  children_count: number
  summary: Stat[]
  segments: Segment[]
  markers: Marker[]
  applications: Application[]
  warnings: string[]
  assumptions: string[]
}

export interface ChatRequest {
  message: string
  history: unknown[]
  scenario?: Scenario
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
  | { type: 'done'; history: unknown[] }
  | { type: 'error'; message: string }
