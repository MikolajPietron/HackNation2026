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
 * The request forms also quote two regulations (article: "§ 15 ust. 1", "zał. 6"):
 * 'rozp_wnioski' (11.03.2025, the leave requests) and 'rozp_zasilki' (27.09.2026, the documents
 * for the benefits).
 */
export interface SourceRef {
  doc: 'przewodnik' | 'kp' | 'ustawa' | 'zalacznik' | 'rozp_wnioski' | 'rozp_zasilki'
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
  // --- Contribution debt (engine/debt.py; ustawa zasiłkowa art. 2a) ---
  /** A parent with a business: social insurance contribution debt on the day the right arises,
   *  in PLN, from a ZUS document (example cases only; the interview does not ask). */
  mother_contribution_debt: number | null
  father_contribution_debt: number | null
  // --- end contribution debt ---
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
  /** F10: after this day a right is lost for good (a padlock with a countdown). */
  irreversible: Irreversible | null
}

// --- F9 "Zostawiacie na stole", F10 "Punkty bez powrotu" (ZADANIA B.8; engine/leftover.py) ---

/**
 * A point of no return: `rate-815-deadline`, `paternity-deadline`, `parental-deadline`.
 * `days_left`: from today to the marker's day; 0 = today is the last day, negative = passed.
 */
export interface Irreversible {
  /** What is lost after that day, one sentence. */
  lost: string
  days_left: number
  /** The quotes that say so (a subset of the marker's sources). */
  sources: SourceRef[]
}

/**
 * Something the family can still use and loses if they do nothing, the soonest first in
 * `Timeline.left_on_table`. Ids: `left-parental`, `left-parental-father`, `left-paternity`,
 * `left-supplementary` (the option on the timeline, `segment_id`), `left-parental-pool` (weeks a
 * plan leaves out) and `left-rate-815` (kind `choice`: the request for 81,5%). Empty after the
 * loss of a child or the mother's death.
 */
export interface Leftover {
  id: string
  /** leave = days not used yet; choice = an option that closes on `last_day`. */
  kind: 'leave' | 'choice'
  /** Whose right; null = either parent. */
  parent: Role | null
  title: string
  text: string
  /** Days that can still be used; null for a choice. */
  days: number | null
  /**
   * PLN lost if nothing is done: the benefit for those days; for a choice, how much more the
   * other option pays (0 when it pays no more). null = no base known yet.
   */
  amount: number | null
  /** The last day it can still be used (for a choice: the request filed). */
  last_day: string
  /** The last day to start so that all `days` fit before `last_day`. */
  start_by: string | null
  segment_id: string | null
  /** The point of no return on the timeline, when there is one. */
  marker_id: string | null
  sources: SourceRef[]
}

// --- end F9, F10 ---

// Request forms (ZADANIA B.3, backend/app/engine/forms.py): each request on the timeline as a
// form to fill in. Only what the sources name: the regulation on the leave requests
// ('rozp_wnioski') and the annexes of the regulation on the benefit documents ('rozp_zasilki':
// annex 6 = the data of ZAM, annex 1 = the sickness benefit). The ZUS forms themselves (ZAM,
// ZAS-53) are on www.zus.pl, not in our materials.

/**
 * text = words or numbers; date = one day (`start`); period = from `start` to `end`;
 * statement = a declaration the person makes in the request (`value` says what it is about).
 */
export type FormFieldKind = 'text' | 'date' | 'period' | 'statement'

/**
 * Who the request goes to: the employer; the payer of contributions (the principal of a contract
 * of mandate) that pays the benefit itself; ZUS; the payer or ZUS (the payer's size not known).
 */
export type Addressee = 'employer' | 'payer' | 'zus' | 'payer-or-zus'

export interface FormField {
  /** Stable within the form, e.g. "employee-name", "leave-period", "child-birth-date". */
  id: string
  label: string
  kind: FormFieldKind
  /** Filled in by the app, in Polish (dates DD.MM.RRRR); null = the person types it in. */
  value: string | null
  /** The filled value as dates: kind "date" — `start`; kind "period" — `start` to `end`. */
  start: string | null
  end: string | null
  /** Personal data (names, PESEL, addresses, NIP, bank account, signature): never filled in. */
  personal: boolean
  /** false = only in the case the source names (e.g. "jeżeli są niezbędne"). */
  required: boolean
  /** Where the value comes from, or what to write in. */
  hint: string | null
  sources: SourceRef[]
}

export interface FormAttachment {
  id: string
  label: string
  /** false = only in the case `hint` describes (e.g. when the payer, not ZUS, pays). */
  required: boolean
  hint: string | null
  sources: SourceRef[]
}

/** A line about the whole request, e.g. that the ZUS form is on www.zus.pl. */
export interface FormNote {
  text: string
  sources: SourceRef[]
}

export interface RequestForm {
  title: string
  applicant: Role
  addressee: Addressee
  /** "Pracodawca mamy", "ZUS", "Płatnik składek (zleceniodawca) albo ZUS". */
  addressee_label: string
  /** "ZAM", "ZAS-53" (on www.zus.pl); null = a request the employee writes. */
  official_form: string | null
  /** The provisions that name this request and say what it contains. */
  legal_basis: SourceRef[]
  /** The period on the timeline the request is for. */
  start: string | null
  end: string | null
  fields: FormField[]
  attachments: FormAttachment[]
  notes: FormNote[]
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
  /**
   * The last day to file it under a Labour Code deadline, for the day on the timeline (may have
   * passed). null = the materials give no deadline: `needed_by` is only the day the leave, the
   * benefit or the sick leave starts — show it as "na dzień startu", never as a deadline.
   */
  deadline: string | null
  /** The request as a form to fill in; null for documents that are not requests. */
  form: RequestForm | null
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

// --- F4 Wypłaty miesiąc po miesiącu (ZADANIA B.12; engine/monthly.py) ---

/**
 * Who pays the money out: employer = the employer's own sick pay in pregnancy (wynagrodzenie
 * chorobowe); payer = the payer of contributions pays the benefit itself (more than 20 insured:
 * an employee's employer, the principal of a contract of mandate); zus = ZUS; payer-or-zus = the
 * payer or ZUS, by how many people the payer reports (not known yet).
 */
export type PaidBy = 'employer' | 'payer' | 'zus' | 'payer-or-zus'

/** One parent's money in one calendar month from one payer. */
export interface MonthlyLine {
  parent: 'mother' | 'father'
  /** null = the materials do not say who pays it (the rehabilitation benefit). */
  payer: PaidBy | null
  /**
   * Ready to show: "Pracodawca mamy (wynagrodzenie chorobowe)", "Pracodawca mamy", "ZUS",
   * "Zleceniodawca taty albo ZUS", "Materiały nie mówią, kto wypłaca".
   */
  payer_label: string
  /** For each payment in `payment_ids`: its daily amount × its days in this month. */
  amount: number
  /** `Timeline.payments` ids with days in this month, the earliest first. */
  payment_ids: string[]
}

/**
 * The money for the days of one calendar month (not the day it reaches the account). Every
 * month from the first paid day to the last is listed; a month without a paid day (a gap) has
 * `total` 0 and no lines. The engine computes every amount: do not add them up in the front.
 */
export interface MonthlyPayment {
  /** "2027-03". */
  month: string
  mother: number
  father: number
  /** `mother` + `father`. */
  total: number
  /**
   * Who pays each parent this month: the mother's lines first, then the father's; more than one
   * for a parent when the month mixes payers (sick pay from the employer, then ZUS).
   */
  lines: MonthlyLine[]
  /** Every payment with days in this month, the earliest first. */
  payment_ids: string[]
}

/** All payments together (the sum of `Timeline.payments`, and of `Timeline.monthly`). */
export interface MoneyTotal {
  total: number
  mother: number
  father: number
}

// --- end F4 ---

/**
 * One point of the case explanation: situation = which case this is, right = what the mother is
 * entitled to, risk = what stands in the way of an entitlement, choice = what the family can
 * decide, relief = an easier or longer path the rules give them, computed = what we calculated.
 * F14 "Nie przysługuje" z dalszą drogą: `insurance-way`, `father-way`, `taken-in-way` (kind risk,
 * right after the point that says there is no right): "Co zamiast: …" and "Co zrobić, żeby
 * przysługiwał: …" (engine/no_right.py).
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
  /** F9: what the family can still use and loses if they do nothing (see `Leftover`). */
  left_on_table: Leftover[]
  /** F4: `payments` month by month, gaps included (see `MonthlyPayment`); empty without them. */
  monthly: MonthlyPayment[]
  /** F4: all `payments` together; null without payments. */
  money_total: MoneyTotal | null
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

/**
 * Fields of the scenario the interface changes without the chat (`PATCH
 * /api/session/{id}/scenario`): e.g. `parental_parts`, `rate_815`, `job_loss`,
 * `mother_pay_history`. A field given replaces the saved one; null clears it.
 */
export type ScenarioChanges = Partial<Scenario>

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
  | { type: 'done'; usage?: TurnUsage }
  | { type: 'error'; message: string }

/** Time and tokens of one chat turn (api/chat.py `_Translator._measure`), for tools/eval; the UI
 * does not need it. `input_tokens` include the cached ones; `cost_usd` is null for a model
 * without a known price. */
export interface TurnUsage {
  first_text_s: number | null
  total_s: number
  requests: number
  input_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  output_tokens: number
  cost_usd: number | null
}

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
/**
 * Why the calculator and ZUS differ: reading = the facts as read lack or contradict what the
 * decision rests on (read the case again); missing-rule = the calculator has no rule for it;
 * other-refusal = ZUS refused for a reason the calculator does not check (documents, deadlines).
 */
export type DifferenceReason = 'reading' | 'missing-rule' | 'other-refusal'
/** What ZUS established about an insurance period: a sham contract or business, or no sickness
 *  insurance for another reason. */
export type ZusFinding = 'sham' | 'not-subject'

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
  /** A finding of ZUS wins over what the payer declared: the period gives no sickness insurance. */
  zus_finding: ZusFinding | null
  pages: number[]
}

export interface LeavePeriod {
  person: Role
  kind: LeaveKind
  start: string
  end: string | null
  pages: number[]
}

/** A month of pay as read from the case (Z-3, Z-3a); not the engine's `PayMonth`. */
export interface CasePayMonth {
  month: string
  amount: number
  kind: 'salary' | 'contribution_base'
  person: Role
  full_month: boolean | null
  /** A month not worked in full: days required and days worked, as in Z-3. */
  days_required: number | null
  days_worked: number | null
  /** Only when Z-3 gives them apart: fixed pay from the contract, variable pay, overtime etc. */
  fixed: number | null
  variable: number | null
  not_topped: number | null
  note: string
  pages: number[]
}

/** A quarterly or annual bonus from Z-3, as listed there (the calculator sums them). */
export interface CaseBonus {
  person: Role
  kind: 'quarterly' | 'annual'
  period: string
  amount: number
  pages: number[]
}

/** What else the benefit base depends on: full time, the start of insurance, the contract pay. */
export interface CasePayDetails {
  person: Role
  full_time: boolean | null
  insured_from: string | null
  contract_pay: number | null
  pages: number[]
}

/** The mother's work ended in pregnancy (becomes `Scenario.job_loss`). */
export interface CaseJobLoss {
  ended_on: string
  reason: JobLossReason
  court_confirmed: boolean | null
  pages: number[]
}

/** A special situation of the mother (becomes `Scenario.mother_event`). */
export interface CaseMotherEvent {
  kind: MotherEventKind
  start: string
  end: string | null
  pages: number[]
}

/** Contribution debt of a person with a business, from a ZUS document (ustawa art. 2a). */
export interface CaseContributionDebt {
  person: Role
  amount: number
  /** The day the document gives the debt for. */
  on: string | null
  repaid_on: string | null
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
  pay: CasePayMonth[]
  bonuses: CaseBonus[]
  pay_details: CasePayDetails[]
  job_loss: CaseJobLoss | null
  mother_event: CaseMotherEvent | null
  contribution_debt: CaseContributionDebt | null
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
  /** Set when `match` is false. */
  reason: DifferenceReason | null
  /** The difference in a sentence or two, for the agreement report. */
  reason_text: string
}

/** One catalogue case in the agreement report (GET /api/cases/agreement, cache only). */
export interface CaseAgreementRow {
  id: string
  category: string
  /** Read already (in the cache); the other fields are empty until then. */
  read: boolean
  title: string
  zus: CaseOutcome | null
  ours: CaseOutcome | null
  match: boolean | null
  reason: DifferenceReason | null
  reason_text: string
  covered: boolean | null
  timeline: boolean
  payments: number
  problem: string | null
}

/** "Zgodność z decyzjami ZUS: agree/decided", from the cases already read; nothing is read. */
export interface CaseAgreement {
  configured: boolean
  total: number
  read: number
  /** Cases where both the calculator and ZUS have an answer. */
  decided: number
  agree: number
  /** The decisions of ZUS among the cases read. */
  zus: Partial<Record<CaseOutcome, number>>
  /** The differences by reason. */
  reasons: Partial<Record<DifferenceReason, number>>
  with_timeline: number
  with_amounts: number
  rows: CaseAgreementRow[]
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

// Letters from ZUS (F24, AI) and the request check (F23): backend/app/letters,
// app/request_check, api/letters.py, api/request_check.py

/** A ZUS form the guide names (pages 3, 6, 12). ZUR, ZAO and Z-3b are abolished since 24.10.2026. */
export interface KnownForm {
  code: string
  name: string
  abolished: boolean
  /** The form it was merged into (ZUR and ZAO: ZAM). */
  merged_into: string | null
  sources: SourceRef[]
}

/** decision = decyzja, summons = wezwanie, notice = zawiadomienie, information = informacja. */
export type LetterKind = 'decision' | 'summons' | 'notice' | 'information' | 'other'
export type LetterOutcome = 'granted' | 'refused' | 'partial' | 'changed' | 'none'
/** job_loss = zasiłek w wysokości zasiłku macierzyńskiego; rate_815 = zasiłek 81,5%. */
export type LetterBenefit =
  | 'maternity'
  | 'parental'
  | 'paternity'
  | 'supplementary'
  | 'sickness'
  | 'rehabilitation'
  | 'job_loss'
  | 'rate_815'
  | 'other'

/** A literal fragment of the letter (personal data replaced with "[…]"). */
export interface LetterQuote {
  text: string
  page: number
}

export interface LetterItem {
  text: string
  quote: LetterQuote
}

export interface LetterAction {
  what: string
  /** The deadline in the letter's words, e.g. "w terminie 7 dni od dnia doręczenia pisma". */
  deadline_text: string | null
  /** Only a date written in the letter (checked against its quote); never computed. */
  deadline_date: string | null
  quote: LetterQuote
}

export interface LetterPeriod {
  benefit: LetterBenefit
  start: string | null
  end: string | null
  quote: LetterQuote
}

/** A letter from ZUS in plain Polish. Always AI: label it in the UI with `ai_label`. */
export interface LetterExplanation {
  ai: true
  ai_label: string
  /** The model that read the letter (Claude or Gemini). */
  model: string
  is_zus_letter: boolean
  kind: LetterKind
  kind_label: string
  heading: string
  subject: string
  outcome: LetterOutcome
  outcome_label: string | null
  summary: string
  reason: LetterItem | null
  /** The letter asks the parent to do something (`actions` not empty). */
  action_needed: boolean
  actions: LetterAction[]
  prepare: LetterItem[]
  periods: LetterPeriod[]
  /** How and by when to appeal, when the letter says so: a right, not a duty. */
  appeal: LetterAction | null
  forms: KnownForm[]
  /** Form codes in the letter that the guide does not describe. */
  other_forms: string[]
  /** Timeline element ids the letter is about (with a session: only those on its timeline). */
  timeline_elements: string[]
  quotes: LetterQuote[]
  pages: number
  pages_read: number
  personal_data_removed: boolean
  warnings: string[]
  unreadable: string[]
}

/** What a request field means for the check; inferred from the label when not given. */
export type RequestFieldKey =
  | 'start'
  | 'end'
  | 'period'
  | 'weeks'
  | 'return_to_work'
  | 'maternity_end'
  | 'birth_date'
  | 'filed_on'
  | 'rate_815'

/** One labelled field of a filled request (the request form's shape: label, value, source). */
export interface RequestField {
  label: string
  value: string | null
  source?: string | null
  key?: RequestFieldKey | null
  /** The field's id in the timeline's form (`FormField.id`): its meaning is known, not guessed. */
  id?: string | null
  /** An empty required field is a problem; default true. */
  required?: boolean
}

export interface FilledRequest {
  title: string
  addressee?: string | null
  fields: RequestField[]
  attachments?: string[]
  /** The timeline document the request is for, e.g. "parental-request". */
  form_id?: string | null
  parent?: Role | null
  /** Default: a "data złożenia" field, else today. */
  filed_on?: string | null
}

export interface RequestCheckRequest {
  request: FilledRequest
  /** The session whose timeline the dates are checked against. */
  session_id?: string | null
  /** Instead of a session (e.g. an example case). */
  scenario?: Scenario | null
  /** Ask the AI to reword the problems (it finds none and adds no rules). */
  phrase?: boolean
}

export type RequestKind =
  | 'maternity-request'
  | 'maternity-father-request'
  | 'maternity-resignation'
  | 'supplementary-request'
  | 'parental-request'
  | 'parental-father-request'
  /** ZADANIA B.13: combining parental leave with work (documents `parental-work-request-<k>`,
   *  `parental-father-work-request-<k>`); its deadline is 21 days before the work starts. */
  | 'parental-work-request'
  | 'paternity-request'
  | 'zam'
  | 'rate-815'
  | 'zas-53'
  | 'unknown'

/**
 * form-abolished = ZUR, ZAO, Z-3b after 24.10.2026; field-empty; dates-order = ends before it
 * starts; weeks-mismatch; deadline-passed = Labour Code days before the leave; leave-order =
 * parental before maternity ends, supplementary not right after it; after-limit = after the last
 * possible day; rate-815-late; differs-from-plan; attachment-missing (A.4); wrong-addressee;
 * unknown-form and no-timeline = what could not be checked.
 */
export type RequestCheckKind =
  | 'form-abolished'
  | 'field-empty'
  | 'dates-order'
  | 'weeks-mismatch'
  | 'deadline-passed'
  | 'leave-order'
  | 'after-limit'
  | 'rate-815-late'
  | 'differs-from-plan'
  | 'attachment-missing'
  | 'wrong-addressee'
  | 'unknown-form'
  | 'no-timeline'

export type RequestSeverity = 'error' | 'warning' | 'info'

export interface RequestProblem {
  id: string
  check: RequestCheckKind
  severity: RequestSeverity
  /** The label of the field it is about. */
  field: string | null
  /** Found and worded by the app, without AI. */
  message: string
  sources: SourceRef[]
  /** The timeline element it is about, to highlight. */
  element_id: string | null
  /** The same problem reworded by AI (only with `phrase`): label it as AI. */
  phrased: string | null
}

export interface RequestCheckResult {
  kind: RequestKind
  kind_label: string
  recognized: boolean
  /** No errors. */
  ok: boolean
  problems: RequestProblem[]
  /** The checks that ran. */
  checks: RequestCheckKind[]
  timeline_used: boolean
  /** True only when AI reworded the problems. */
  ai: boolean
  ai_model: string | null
  ai_note: string | null
  filed_on: string
}
