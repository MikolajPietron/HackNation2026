// Mirrors backend/app/engine/models.py and the /api/chat event protocol. Keep in sync.
// Phases 1-3: guide section A, "Przygotowanie do porodu", "Urodzenie dziecka" and the stillbirth
// or death of the child (pages 5-6). Section B: the father (pages 7-8).

export type Lane = 'mother' | 'father' | 'child' | 'documents'
/** leave = leave a parent takes, work = the mother keeps working, option = possible, not decided. */
export type Tone = 'leave' | 'work' | 'option'

export type Role = 'mother' | 'father'
export type Work = 'employment' | 'contract' | 'business' | 'none'
export type Earnings = 'under-5k' | '5k-8k' | '8k-12k' | 'over-12k' | 'unknown'
/** When the child was born, as the Labour Code art. 180² § 1 divides it (weeks of pregnancy). */
export type BirthWeek = 'before-28' | '28-37' | 'after-37'
/**
 * Guide section D: adoption = took the child in and asked the court to start adoption
 * proceedings; foster = a non-professional foster family.
 */
export type TakenIn = 'adoption' | 'foster'

/**
 * A literal quote: from the guide (section and pages), from the Labour Code ('kp') or from the
 * ustawa zasiłkowa ('ustawa'; both: article), or from the ZUS Załącznik ('zalacznik': section).
 */
export interface SourceRef {
  doc: 'przewodnik' | 'kp' | 'ustawa' | 'zalacznik'
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

/**
 * Guide section B, "Sytuacje szczególne": the mother has a certificate of inability to live
 * independently, is in hospital, died, or abandoned the child.
 */
export type MotherEventKind = 'incapacity' | 'hospital' | 'death' | 'abandonment'

/** A special situation in which the father takes over maternity leave early. */
export interface MotherEvent {
  kind: MotherEventKind
  /**
   * Incapacity: the day the father takes over; hospital: the first day in hospital; death,
   * abandonment: the day it happened.
   */
  start: string
  /** Hospital only: the last day in hospital; null = still there. */
  end: string | null
}

/**
 * How many people the payer (employer, or the principal of a contract of mandate) reports to
 * sickness insurance: more than 20 = it pays the benefit itself, otherwise ZUS (guide page 1).
 */
export type PayerSize = 'over-20' | 'up-to-20' | 'unknown'

/**
 * One part of parental leave as the parents plan it (guide sections B.3 and E). The engine
 * gives it dates and draws it as `parental-mother-<k>` / `parental-father-<k>`.
 */
export interface ParentalPart {
  parent: Role
  /** Weeks taken from the pool, without the extension from working. */
  weeks: number
  /** null = right after the previous part of the plan. */
  start: string | null
  /** Starts on the same day as the previous part: both parents at once. */
  with_previous: boolean
  /** Part-time work as a fraction of full time, e.g. "1/2"; null = no work. */
  work_fraction: string | null
  /** Weeks combined with work from the first day of the part; null = the whole part. */
  work_weeks: number | null
}

/** What the onboarding and the interview have established. null = not known yet. */
export interface Scenario {
  /** The person filling in. Work and earnings are that person's own. */
  role: Role | null
  work: Work | null
  earnings: Earnings | null
  /** How the mother works, when somebody else fills in. */
  mother_work: Work | null
  /** How the father works, when somebody else fills in. */
  father_work: Work | null
  child_born: boolean | null
  due_date: string | null
  birth_date: string | null
  children_count: number | null
  leave_before_birth_weeks: number | null
  has_medical_certificate: boolean | null
  /** The real first day of leave before the birth, carried over from the plan at the birth. */
  leave_start: string | null
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
  /** Voluntary sickness insurance of a father on a contract or with his own business. */
  father_insured: boolean | null
  /** The mother leaves the rest of maternity leave to the father after at least 14 weeks. */
  father_takes_over: boolean | null
  /** Weeks after the birth the mother uses before the father takes over (default 14). */
  mother_weeks_before_takeover: number | null
  mother_event: MotherEvent | null
  // Applications and protection (guide A.4, I)
  /** The mother's employer (principal): more than 20 insured or not; not asked for a business. */
  mother_payer_size: PayerSize | null
  father_payer_size: PayerSize | null
  // Pregnancy (guide: sickness benefit, job loss, risks)
  /** The mother is (or was) on sick leave in this pregnancy. */
  sick_leave: boolean | null
  sick_leave_start: string | null
  /** The last day of the sick leave; null = until the birth. */
  sick_leave_end: string | null
  /** The first day of the mother's uninterrupted sickness insurance (the 30 or 90 days). */
  insured_since: string | null
  /** Her contract or business began during this pregnancy (guide section H, risk 1). */
  insured_in_pregnancy: boolean | null
  /** An employed mother turned 50 before the calendar year of the sick leave. */
  mother_over_50: boolean | null
  /** She raised the base of her contributions in pregnancy (section H, risk 2). */
  contribution_base_raised: boolean | null
  /** Recorded only when the parent says so. */
  job_loss: JobLoss | null
  // Parental leave with work (guide section E)
  /** How the parents split parental leave and where they work part-time; [] = no plan. */
  parental_parts: ParentalPart[]
  // Adoption and foster care (guide section D).
  /** The child was taken in for upbringing: `birth_date` is then the child's date of birth. */
  taken_in: TakenIn | null
  /** The day of taking in (adoption: and of the court application, the later of the two). */
  taken_in_on: string | null
  /** Foster care: compulsory schooling was postponed (age limit 10, not 7). */
  school_postponed: boolean | null
  /** Adoption: the adoption ruling is final, since `adoption_final_on`. */
  adoption_final: boolean | null
  adoption_final_on: string | null
  // Amounts (guide section G).
  /**
   * The mother's monthly amount in PLN as given in the chat: gross salary (employee) or the base
   * of the sickness contribution (contract, business). 'unknown' = not given.
   */
  mother_pay: number | 'unknown' | null
  father_pay: number | 'unknown' | null
  /** The mother files the request for 81,5% within 21 days after the birth (false = 100%/70%). */
  rate_815: boolean | null
  // The rehabilitation benefit after 270 days of sick leave in pregnancy (ustawa art. 18-19).
  /** Recorded only when the parent says so: applied for, granted or refused. */
  rehab_benefit: RehabStatus | null
  /** The last day of the period it was granted for, when the parent gave it. */
  rehab_benefit_end: string | null
  // Adoption and foster care, edge cases (Labour Code art. 183 § 2, § 7-§ 8).
  /** The rest of the leave on the terms of maternity leave passes to the other parent. */
  taken_in_handover: boolean | null
  /** Weeks used before passing it on; null = 14. */
  taken_in_handover_after_weeks: number | null
  /** Adoption after foster care: the leave already used as a foster family. */
  foster_before: FosterBefore | null
  // The benefit base in detail (engine/base.py): the payer's certificate (Z-3, Z-3a) typed in.
  /** Months given win over `mother_pay`; the other fields apply either way. */
  mother_pay_history: PayHistory | null
  father_pay_history: PayHistory | null
}

/** Applied for (no decision yet), granted or refused. */
export type RehabStatus = 'applied' | 'granted' | 'refused'

/** Adoption after foster care (Labour Code art. 183 § 7-§ 8). */
export interface FosterBefore {
  /** The leave on the terms of maternity leave used as a foster family: first and last day. */
  leave_start: string | null
  leave_end: string | null
  /** Weeks of parental leave used as a foster family. */
  parental_weeks: number | null
}

/** One calendar month of pay before the right to the benefit, as the payer's certificate gives it. */
export interface PayMonth {
  /** "2026-03" */
  month: string
  /** PLN. Employee: gross pay for the month (no quarterly or annual bonuses); else the contribution base. */
  amount: number
  /** A month not worked in full: days required and days worked (a non-employee: days of the month). */
  days_required: number | null
  days_worked: number | null
  /** Employee, a month in part: the fixed monthly pay from the contract, taken in full. */
  fixed: number | null
  /** Employee, with `fixed`: the variable pay for the days worked, topped up by days. */
  variable: number | null
  /** Employee: overtime, night work, commission — as paid, never topped up. */
  not_topped: number | null
}

export interface PayHistory {
  months: PayMonth[]
  /** Quarterly bonuses paid for the four quarters before the month of the right, together. */
  quarterly_bonuses: number | null
  /** Annual pay (thirteenth salary, annual award) for the year before the month of the right. */
  annual_bonus: number | null
  /** Full-time work: the base is not lower than the minimum. */
  full_time: boolean | null
  /** The first day of insurance with this payer; null = not known. */
  insured_from: string | null
  /** The monthly pay in the contract: the base in the first month of insurance. */
  contract_pay: number | null
}

/**
 * Why the mother's work ended in pregnancy: the employer's bankruptcy, liquidation or death, a
 * termination that broke the law (guide p. 4), or any other end of work (section H, risk 3).
 */
export type JobLossReason = 'bankruptcy' | 'liquidation' | 'employer-death' | 'unlawful' | 'other'

/** The mother's work ended in pregnancy. */
export interface JobLoss {
  /** The last day of the employment (or of the contract or business). */
  ended_on: string
  reason: JobLossReason
  /** Unlawful termination only: a final court judgment confirmed it. */
  court_confirmed: boolean | null
}

/** What the onboarding learned about one parent's work. null = not asked, or "nie wiem". */
export interface WorkFacts {
  work: Work | null
  /** Contract or business only: registered for the voluntary sickness insurance. */
  insured: boolean | null
  /** Employment or contract only: does the payer report more than 20 people? */
  payer_size: PayerSize | null
  /** Gross salary (employee) or the base of the sickness contribution, per month, in PLN. */
  pay: number | 'unknown' | null
}

/** Everything the onboarding asks, as sent to PUT /api/session/{id}/onboarding. `work`,
 *  `insured`, `payer_size` and `pay` are the respondent's own; `partner` is the other parent. */
export interface OnboardingAnswers {
  role: Role
  child_born: boolean
  /** Date of birth when `child_born`, otherwise the expected due date. */
  date: string
  children_count: number
  work: Work
  insured?: boolean | null
  payer_size?: PayerSize | null
  pay?: number | 'unknown' | null
  partner?: WorkFacts
  /** No longer asked (the range gave no amounts); kept by the backend for older clients. */
  earnings?: Earnings | null
  /** A child taken in for upbringing: then `child_born` is true and `date` the child's birth. */
  taken_in?: { kind: TakenIn; date: string } | null
  /** Born child: premature or in hospital after the birth (the chat asks the details). */
  hospital_care?: boolean | null
  /** Born child: weeks of maternity leave the mother took before the birth (0 = none). */
  leave_before_birth_weeks?: number | null
  /** Child on the way: the mother's sick leave in this pregnancy; no end = until the birth. */
  sick_leave?: boolean | null
  sick_leave_start?: string | null
  sick_leave_end?: string | null
  /** The mother's uninterrupted sickness insurance since (from the simulated ZUS data). */
  insured_since?: string | null
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
 * The maternity benefit for one period on the timeline (guide section G), the "Pieniądze" lane.
 * Amounts in PLN, rounded to grosze; `segment_id` is the period it pays for.
 */
export interface Payment {
  id: string
  segment_id: string
  lane: 'mother' | 'father'
  title: string
  start: string
  end: string
  days: number
  /** Percent of the benefit base: 100, 70 or 81.5. */
  rate: number
  /** Monthly benefit base (podstawa wymiaru zasiłku). */
  base: number
  monthly: number
  daily: number
  total: number
  summary: string
  /** The calculation, step by step. */
  details: string[]
  sources: SourceRef[]
}

/** One step of computing a benefit base ("Dlaczego tyle?"), with the rules it applies. */
export interface BaseStep {
  text: string
  sources: SourceRef[]
}

/**
 * full = taken as paid; topped-up = worked at least half, topped up; skipped = worked less than
 * half; outside = not among the months of the base; before-insurance = before insurance began.
 */
export type BaseMonthStatus = 'full' | 'topped-up' | 'skipped' | 'outside' | 'before-insurance'

export interface BaseMonth {
  month: string
  amount: number
  /** What enters the average; null = not counted. */
  counted: number | null
  status: BaseMonthStatus
}

/** One parent's monthly benefit base and how it was computed, step by step (engine/base.py). */
export interface BenefitBase {
  parent: 'mother' | 'father'
  work: Work
  /** The day the right arose that the base is set for. */
  right_from: string
  /** The months the base comes from ("2025-11" to "2026-10"); null = from the contract. */
  months_from: string | null
  months_to: string | null
  /** The monthly average before the deduction (with a twelfth of bonuses). */
  pay: number
  /** Percent deducted for the contributions (13,71). */
  deducted: number
  /** The monthly benefit base. */
  base: number
  /** Computed from the months given, not from one monthly amount. */
  detailed: boolean
  /** The base in one sentence, after "Podstawa wymiaru zasiłku: ". */
  summary: string
  steps: BaseStep[]
  months: BaseMonth[]
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
  /** Set for a child taken in for upbringing: then `birth_date` is the day of taking in. */
  taken_in: TakenIn | null
  /** Section G: the benefit for each period, once the parent's monthly amount is known. */
  payments: Payment[]
  /** Each parent's benefit base behind `payments`, step by step. */
  bases: BenefitBase[]
}

/** An app event the assistant reacts to instead of a message; the user does not see it. */
export type AppEvent = 'timeline_ready'

/** A user message or an app event, one of the two. */
export interface ChatRequest {
  session_id: string
  message?: string
  event?: AppEvent
}

/** The next interview question, as the assistant asks it; `key` picks the answer cards. */
export interface InterviewQuestion {
  key: string
  text: string
}

/** A stored conversation, as returned by GET /api/session/{id}. */
export interface SessionView {
  messages: StoredMessage[]
  scenario: Scenario
  timeline: Timeline | null
  question: InterviewQuestion | null
}

/** The onboarding answers as stored, and the first timeline. */
export interface SessionStart {
  scenario: Scenario
  timeline: Timeline
  question: InterviewQuestion | null
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
      question: InterviewQuestion | null
    }
  | { type: 'focus'; element_id: string }
  | { type: 'done' }
  | { type: 'error'; message: string }

// Admin panel (backend/app/api/admin.py).

export interface Param<T> {
  value: T
  note: string | null
  sources: SourceRef[]
}

/** The legal parameters as the engine gets them (backend/app/engine/params.py). */
export interface Params {
  version: string
  description: string
  maternity: {
    max_weeks_before_birth: Param<number>
    weeks_by_children: Param<number[]>
    mother_personal_weeks: Param<number>
  }
  /** Guide section G: the rates of the benefit and the 81,5% request (only what the panel uses). */
  money: {
    rate_full: Param<number>
    rate_parental: Param<number>
    rate_single: Param<number>
    request_days: Param<number>
  }
  /** The deadlines of the requests (only what the panel uses). */
  applications: {
    parental_days_before: Param<number>
    paternity_days_before: Param<number>
    supplementary_days_before_end: Param<number>
  }
  rules: Record<string, { sources: SourceRef[] }>
}

/** The numbers the admin panel can change (backend/app/api/admin.py `ParamValues`). */
export interface ParamValues {
  max_weeks_before_birth: number
  weeks_by_children: number[]
  mother_personal_weeks: number
  /** Percent of the base: maternity, supplementary and paternity leave. */
  rate_full: number
  /** Percent of the base: parental leave. */
  rate_parental: number
  /** Percent of the base after the mother's request (81,5%). */
  rate_single: number
  /** The request for the single rate: at the latest this many days after the birth. */
  rate_single_request_days: number
  /** Requests for leave: at least this many days before. */
  parental_request_days: number
  paternity_request_days: number
  /** At least this many days before maternity leave ends. */
  supplementary_request_days: number
}

export interface ParamVersion {
  id: string
  version: string
  effective_from: string
  note: string
  created_at: string
  values: ParamValues
  status: 'in_force' | 'scheduled' | 'past'
}

export interface AdminView {
  today: string
  base: Params
  in_force: ParamValues
  /** Newest first. */
  versions: ParamVersion[]
}

export interface ParamPreview {
  before: Timeline
  after: Timeline
}

// ---------------------------------------------------------------------------------------------
// Example cases from ZUS (backend/app/cases/models.py, api/cases.py)

export type InsuranceTitle = 'employment' | 'contract' | 'business' | 'other'
export type SicknessInsurance = 'mandatory' | 'voluntary' | 'none' | 'unknown'
export type LeaveKind = 'maternity' | 'parental' | 'paternity' | 'supplementary' | 'sick' | 'other'
export type CaseOutcome = 'granted' | 'refused' | 'partial' | 'unknown'

export interface CaseDocument {
  kind: string
  pages: number[]
}

export interface InsurancePeriod {
  person: Role
  title: InsuranceTitle
  label: string
  start: string | null
  end: string | null
  sickness: SicknessInsurance
  pages: number[]
}

export interface LeavePeriod {
  person: Role
  kind: LeaveKind
  start: string
  end: string | null
  pages: number[]
}

export interface PayMonth {
  month: string
  amount: number
  kind: 'salary' | 'contribution_base'
  person: Role
  full_month: boolean | null
  note: string
  pages: number[]
}

export interface CaseDecision {
  outcome: CaseOutcome
  benefit: string
  reason: string
  pages: number[]
}

export interface HospitalPeriod {
  start: string
  end: string | null
  pages: number[]
}

/** What the case says, as read from its scans: transcription only, with page numbers. */
export interface CaseFacts {
  /** A short title AI gave the case (empty for cases read before it existed). */
  title: string
  summary: string
  applicant: Role | null
  benefit_requested: string
  child_born: boolean | null
  birth_date: string | null
  due_date: string | null
  children_count: number | null
  stillborn: boolean | null
  taken_in: TakenIn | null
  taken_in_on: string | null
  za_zyciem: boolean | null
  hospital_after_birth: boolean | null
  birth_week: number | null
  birth_weight_grams: number | null
  hospital_stays: HospitalPeriod[]
  payer_over_20: boolean | null
  documents: CaseDocument[]
  insurance: InsurancePeriod[]
  leaves: LeavePeriod[]
  pay: PayMonth[]
  decision: CaseDecision | null
  unreadable: string[]
}

export interface CaseListItem {
  id: string
  category: string
  /** The title AI gave the case once read; empty before. */
  title: string
  pages: number
  read: boolean
}

export interface CaseList {
  configured: boolean
  cases: CaseListItem[]
}

export interface InsuranceCheck {
  person: Role
  on: string | null
  covered: boolean | null
  period: InsurancePeriod | null
  text: string
}

export interface CaseComparison {
  ours: CaseOutcome
  zus: CaseOutcome
  match: boolean | null
  text: string
}

export interface CaseResult {
  id: string | null
  pages: number
  pages_read: number
  cached: boolean
  facts: CaseFacts
  scenario: Scenario
  timeline: Timeline | null
  insurance: InsuranceCheck
  comparison: CaseComparison
  notes: string[]
  problem: string | null
}

// ---------------------------------------------------------------------------------------------
// F8 plans for a goal and F11 the stress test (backend/app/engine/plans.py, stress.py,
// compare.py; POST /api/plans and POST /api/stress). Deterministic, no AI.

export type PlanGoal = 'most-money' | 'longest-home' | 'equal-split' | 'quick-return'

/** The Scenario fields a plan sets; send them as they are to PATCH /api/session/{id}/scenario. */
export type PlanPatch = Pick<
  Scenario,
  'parental_parts' | 'rate_815' | 'father_takes_over' | 'mother_weeks_before_takeover'
>

/**
 * One parent's leave in a plan: maternity, supplementary and paternity leave as drawn, parental
 * leave only where the plan decides it (a share still "do wyboru" is left out).
 */
export interface PlanParentFigures {
  leave_days: number
  /** Days of parental leave combined with part-time work. */
  work_days: number
  first_day: string | null
  last_day: string | null
  /** The first day back at work, also part-time; null = no leave. */
  back_to_work: string | null
  /** PLN for the leave counted; null = no amount known for this parent. */
  total: number | null
}

export interface PlanFigures {
  mother: PlanParentFigures
  father: PlanParentFigures
  /** Both parents' money; null when no amount is known. */
  total: number | null
  amounts_known: boolean
  /** The child is at home with a parent on leave, without a break from the birth, until then. */
  home_until: string | null
  /** Weeks of the parental pool the plan takes, of `pool_total`. */
  pool_used: number
  pool_total: number
  rate_815: boolean | null
}

export interface Plan {
  id: string
  goal: PlanGoal
  /** 1 = the best for the goal. */
  rank: number
  title: string
  summary: string
  patch: PlanPatch
  figures: PlanFigures
  /** What the family gives up or leaves for later with this plan. */
  given_up: string[]
  /** Elements that differ from the current timeline. */
  changed: string[]
  /** The family already has this plan. */
  current: boolean
  sources: SourceRef[]
}

export interface PlansResult {
  goal: PlanGoal
  plans: Plan[]
  /** The same figures for the timeline as it is now. */
  current: PlanFigures | null
  /** What the comparison assumes and cannot compare. */
  notes: string[]
  /** After a child's death or the mother's death: no plans. */
  sensitive: boolean
  /** Why there are no plans. */
  reason: string | null
}

export type StressEventId =
  | 'premature'
  | 'twins'
  | 'job-loss-bankruptcy'
  | 'job-loss-liquidation'
  | 'job-loss-employer-death'
  | 'job-loss-unlawful'
  | 'job-loss-other'
  | 'mother-incapacity'
  | 'mother-hospital'
  | 'mother-death'
  | 'father-takeover'
  | 'za-zyciem'

/**
 * loss = an entitlement lost or shortened, or the plan stops fitting; risk = a new risk; kept =
 * the entitlements stay (possibly moved, longer or new).
 */
export type StressVerdict = 'loss' | 'risk' | 'kept'

export type RightKind =
  | 'maternity'
  | 'supplementary'
  | 'paternity'
  | 'parental'
  | 'job-loss'
  | 'sick'

/** An entitlement gained (days_before 0), lost (days_after 0), longer or shorter: both lanes. */
export interface RightChange {
  kind: RightKind
  label: string
  days_before: number
  days_after: number
}

export interface PeriodChange {
  id: string
  element: 'segment' | 'marker'
  lane: Lane
  title: string
  change: 'added' | 'removed' | 'moved'
  start_before: string | null
  /** null for a marker (its day is `start_before`). */
  end_before: string | null
  start_after: string | null
  end_after: string | null
}

export interface PaymentChange {
  id: string
  title: string
  lane: 'mother' | 'father'
  monthly_before: number | null
  monthly_after: number | null
  total_before: number | null
  total_after: number | null
}

/** All the money on the timeline before and after, PLN. */
export interface MoneyChange {
  total_before: number
  total_after: number
  diff: number
  mother_before: number
  mother_after: number
  father_before: number
  father_after: number
  payments: PaymentChange[]
}

export interface StressEvent {
  id: StressEventId
  title: string
  /** The synthetic facts of the what-if (dates, weeks, weight). */
  assumed: string[]
  /** The Scenario fields the event changes (for a preview only, never to save). */
  patch: Partial<Scenario>
  /** "Today" of the event's timeline; the reference is computed for the real today. */
  as_of: string
  verdict: StressVerdict
  /** The mother's illness, stay in hospital or death: show gently (e.g. collapsed). */
  sensitive: boolean
  /** The parents' plan of parental leave no longer fits: the engine's reason. */
  plan_breaks: string | null
  rights: RightChange[]
  periods: PeriodChange[]
  /** null when amounts are not known. */
  money: MoneyChange | null
  /** New or reworded points of the explanation of kind "risk". */
  risks: CaseNote[]
  warnings: string[]
  changed: string[]
  changed_notes: string[]
  /** The changes in plain Polish, one per line. */
  lines: string[]
  sources: SourceRef[]
  /** Both timelines, only with `timelines: true` in the request. */
  reference: Timeline | null
  timeline: Timeline | null
}

export interface SkippedStressEvent {
  id: StressEventId
  title: string
  reason: string
}

export interface StressReport {
  events: StressEvent[]
  skipped: SkippedStressEvent[]
  /** After a child's death or the mother's death: no what-ifs. */
  sensitive: boolean
  /** Why there are no events. */
  reason: string | null
}
