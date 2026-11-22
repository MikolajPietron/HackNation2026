import type {
  AdminView,
  CaseFacts,
  CaseList,
  CaseResult,
  ChatEvent,
  ChatRequest,
  LetterExplanation,
  OnboardingAnswers,
  ParamPreview,
  ParamValues,
  PlanGoal,
  PlansResult,
  RequestCheckRequest,
  RequestCheckResult,
  Scenario,
  ScenarioChanges,
  SessionStart,
  SessionView,
  StressReport,
} from './types'

/** Empty in dev: Vite forwards /api to the backend. Set VITE_API_URL for a separate API host. */
export const API_URL: string = import.meta.env.VITE_API_URL ?? ''

const OFFLINE = 'Brak połączenia z serwerem. Sprawdź, czy backend działa (npm run dev).'

/** One assistant turn. The backend streams NDJSON: one ChatEvent per line. */
export async function streamChat(
  request: ChatRequest,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error(OFFLINE)
  }
  if (!response.ok || !response.body) {
    throw new Error(await errorDetail(response))
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line) as ChatEvent)
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as ChatEvent)
}

/** The stored conversation and its timeline; empty for a new session. */
export async function fetchSession(sessionId: string): Promise<SessionView> {
  const response = await fetch(`${API_URL}/api/session/${sessionId}`)
  if (!response.ok) throw new Error(await errorDetail(response))
  return (await response.json()) as SessionView
}

/** Onboarding: save all answers in the session; returns them as stored and the timeline. */
export async function submitOnboarding(
  sessionId: string,
  answers: OnboardingAnswers,
  signal?: AbortSignal,
): Promise<SessionStart> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/session/${sessionId}/onboarding`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(answers),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error(OFFLINE)
  }
  if (!response.ok) throw new Error(await errorDetail(response))
  return (await response.json()) as SessionStart
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${API_URL}/api/session/${sessionId}`, { method: 'DELETE' })
}

/** JSON request with the same error handling as the rest of the API. */
async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch (error) {
    if (init?.signal?.aborted) throw error
    throw new Error(OFFLINE)
  }
  if (!response.ok) throw new Error(await errorDetail(response))
  return (await response.json()) as T
}

/** Admin panel: the base parameters, the numbers in force and every saved version. */
export const fetchAdminParams = () => requestJson<AdminView>('/api/admin/params')

/** Save a new version of the parameters, valid from a date. */
export const saveParamVersion = (body: { effective_from: string; note: string; values: ParamValues }) =>
  requestJson<AdminView>('/api/admin/params', { method: 'POST', body: JSON.stringify(body) })

/** The example family's plan with the parameters in force and with the draft. */
export const previewParams = (
  values: ParamValues,
  childrenCount: number,
  rate815: boolean,
  signal?: AbortSignal,
) =>
  requestJson<ParamPreview>('/api/admin/preview', {
    method: 'POST',
    body: JSON.stringify({ values, children_count: childrenCount, rate_815: rate815 }),
    signal,
  })

async function errorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // Not JSON: fall through to the generic message.
  }
  return `Serwer odpowiedział błędem ${response.status}.`
}

// ---------------------------------------------------------------------------------------------
// Example cases from ZUS

/** The catalogue S01–S86: ids and categories (file names stay on the server). */
export const fetchCases = () => requestJson<CaseList>('/api/cases')

/** Read a catalogue case with AI (the first time; then it comes from the server's memory). */
export const readCase = (id: string, signal?: AbortSignal) =>
  requestJson<CaseResult>(`/api/cases/${id}/read`, { method: 'POST', signal })

/** Read an uploaded PDF or photo of a case the same way. */
export async function uploadCase(file: File, signal?: AbortSignal): Promise<CaseResult> {
  const body = new FormData()
  body.append('file', file)
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/cases/upload`, { method: 'POST', body, signal })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error(OFFLINE)
  }
  if (!response.ok) throw new Error(await errorDetail(response))
  return (await response.json()) as CaseResult
}

/** Recalculate after the facts were corrected by hand (no AI). */
export const assessCase = (body: { id: string | null; pages: number; pages_read: number; facts: CaseFacts }) =>
  requestJson<CaseResult>('/api/cases/assess', { method: 'POST', body: JSON.stringify(body) })

/**
 * The interface changes the scenario without the chat (sliders, week tiles, the 81,5% switch):
 * the engine recalculates and validates it like a chat answer; a refused change throws with
 * the Polish message. The chat gets a hidden note of what changed.
 */
export const changeScenario = (sessionId: string, changes: ScenarioChanges) =>
  requestJson<SessionStart>(`/api/session/${sessionId}/scenario`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  })

/** The case becomes the plan: a new conversation from its facts. */
export const loadCaseIntoPlan = (sessionId: string, scenario: Scenario) =>
  requestJson<SessionStart>(`/api/cases/session/${sessionId}`, {
    method: 'PUT',
    body: JSON.stringify({ scenario }),
  })

// ---------------------------------------------------------------------------------------------
// F8 plans for a goal and F11 the stress test (no AI). A chosen plan's `patch` goes to
// PATCH /api/session/{id}/scenario.

/** 2-3 plans for the goal, ranked and compared by the engine. */
export const proposePlans = (scenario: Scenario, goal: PlanGoal, signal?: AbortSignal) =>
  requestJson<PlansResult>('/api/plans', {
    method: 'POST',
    body: JSON.stringify({ scenario, goal }),
    signal,
  })

/** What every event that can still happen would change; `timelines` adds both timelines. */
export const stressTest = (scenario: Scenario, timelines = false, signal?: AbortSignal) =>
  requestJson<StressReport>('/api/stress', {
    method: 'POST',
    body: JSON.stringify({ scenario, timelines }),
    signal,
  })

// Letters from ZUS (F24, AI) and the request check (F23)

/** "Przetłumacz pismo z ZUS": a photo or PDF of a letter in plain Polish (AI; nothing stored). */
export async function explainLetter(
  file: File,
  sessionId?: string | null,
  signal?: AbortSignal,
): Promise<LetterExplanation> {
  const body = new FormData()
  body.append('file', file)
  if (sessionId) body.append('session_id', sessionId)
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/letters/explain`, { method: 'POST', body, signal })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error(OFFLINE)
  }
  if (!response.ok) throw new Error(await errorDetail(response))
  return (await response.json()) as LetterExplanation
}

/** Check a filled request before filing it: no AI, unless `phrase` asks AI to reword. */
export const checkRequest = (body: RequestCheckRequest, signal?: AbortSignal) =>
  requestJson<RequestCheckResult>('/api/requests/check', {
    method: 'POST',
    body: JSON.stringify(body),
    signal,
  })
