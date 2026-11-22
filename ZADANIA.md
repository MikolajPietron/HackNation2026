# Podział pracy i braki z zadania (stan 22.11.2026)

Dwa komputery, dwa agenty. Przed pracą `git pull`, po skończonym punkcie commit i `push`. Zrobiony punkt przenieś do „Zrobione” na dole albo usuń.

| | Komputer A (Wiktor, ta sesja) | Komputer B (drugi agent) |
|---|---|---|
| Zakres | **front**: `frontend/` | **logika**: `backend/` (silnik, wywiad, prompty, odczyt spraw), dane, wdrożenie |
| Gałąź | `ui/plan-redesign` | `main` albo własne gałęzie, scalane do `main` |

Granica: API i modele. Gdy B zmienia model albo endpoint, aktualizuje też `frontend/src/types.ts` (kopia modeli backendu) i pisze tu, co doszło. A nie zmienia logiki w `backend/`; gdy czegoś potrzebuje od backendu, dopisuje to niżej.

Źródło wymagań: `docs/Przewodnik_Rodzica_ZUS.pdf`, sekcje 3 („Oczekiwany rezultat”), 4 („Wymagania formalne”) i 6 („Sposób testowania”). Jury przetestuje demo na części przykładowych spraw i sprawdzi poprawność wyliczeń: „Strona powinna mieć możliwość uploadu/wyboru wybranych wniosków”.

## Komputer B — logika

Zostało (stan 22.11.2026, wieczór):

### 2. Zgodność z decyzjami ZUS na 86 sprawach (cel „X/86”) — wymaga płatnego odczytu
- Kod gotowy (B.1, B.11 w „Zrobione”): odczyt i przełożenie na scenariusz obsługują już utratę pracy, ustalenia ZUS („dla pozoru”, niepodleganie), zadłużenie, części rodzicielskiego, przejęcie urlopu i pełną podstawę z Z-3. Różnice mają kategorię (`reading` / `missing-rule` / `other-refusal`).
- Stare odczyty z `.cases_cache` nie mają nowych pól. Trzeba przeczytać ponownie co najmniej: S21 (`job_loss`), S08 i S09 (`zus_finding`, ostrzejsza reguła „voluntary”), S10 i S04 (`contribution_debt`), sprawy z niepełnymi miesiącami w Z-3 (dni), sprawy z premiami, przejęcie urlopu w sytuacji szczególnej (`mother_event`). S19 i S11 mogą działać już na starych odczytach.
- Potem: `uv run python -m app.cases.batch --jobs 1` (pozostałe 56 spraw i ponowny odczyt powyższych), `--only-cached` dla podsumowania; każdą różnicę opisać.

### 5. Demo online (wymóg formalny) — hosting do ustalenia
- Decyzja (Mikołaj, 22.11.2026): na serwerze demo **nie ma skanów spraw**; jury wgrywa PDF samo, lista spraw pokazuje tylko numery i tematy. Dostawcę hostingu ustalimy później.

### Drobne, gdy będzie czas
- Wniosek o łączenie rodzicielskiego z pracą (rozporządzenie § 16, KP art. 182¹ᵉ § 2) jako dokument z formularzem.
- Terminy ZAM dla osoby niebędącej pracownikiem „przed rozpoczęciem korzystania z zasiłku” (rozporządzenie z 27.09.2026) — do decyzji, czy pokazywać jako termin (CLAUDE.md, „Otwarte pytania”).
- `api/cases.py` mógłby brać model przez `document_model.py` (dziś nie odrzuca modeli innych niż Claude i Gemini).

## Komputer A — front
Zrobione 22.11.2026 (szczegóły w „Zrobione”): pieniądze na planie (F4, F5), raport zgodności (F37), porównanie 100/70 a 81,5% (F12), organizacje wsparcia (F28), wniosek o urlop z wysyłką-atrapą (F22). Dalej:

1. **Plan rodzicielskiego w interfejsie (F6 suwak 0–50% etatu, F13 kafelki tygodni, F3 walidacja na żywo).** Czeka na B.7. Do tego czasu przez czat.
2. **Odpis aktu urodzenia (F35, wymóg zadania).** Atrapa przebiegu gov.pl.
3. **„Co jeśli: Utrata pracy w ciąży” (F7).** Podpiąć przez czat.
4. „Zostawiacie na stole” (F9), punkty bez powrotu (F10), stress-test (F11) — gdy B.8 da dane. „Plany dla Was” (F8, drzewo decyzyjne).

### Potrzebne od B dla frontu
- Opcjonalnie: suma kwot za cały plan i kwoty miesiąc po miesiącu w silniku (np. `Timeline.money_total`, `Timeline.monthly`). Front nie sumuje kwot sam; dziś pokazuje kwoty okresów i zestawienie z punktu `rate-815`.
- B.10: front ma już listę organizacji ze sprawdzonych stron (`frontend/src/lib/support.ts`). Jeśli materiały ZUS wymieniają inne, dopisz je tam ze źródłem.
- Punkty B.7 (endpoint zmiany scenariusza), B.3 (dane wniosków), B.10 (źródło organizacji wsparcia), B.8 (funkcje silnika do narysowania).

## Konfiguracja na komputerze A (tylko `backend/.env`, nie w gicie)
`LLM_PROVIDER=google`, `LLM_MODEL=gemini-flash-latest` (czat), `CASES_MODEL=gemini-pro-latest` (sprawy), `GEMINI_API_KEY`, `CASES_DIR` (folder ze skanami). Klucz OpenRouter nie ma już środków.

## Zrobione
- **Dla frontu (A), 22.11.2026 wieczór — wszystko w `main`, typy w `frontend/src/types.ts`, wywołania w `api.ts`:**
  - **B.3 Wnioski do wypełnienia:** każdy dokument osi ma `form: RequestForm | null` — `title`, `applicant`, `addressee` (`employer` / `payer` / `zus` / `payer-or-zus`) z `addressee_label`, `official_form` (`ZAM`, `ZAS-53` albo null), `legal_basis`, `start`/`end`, `fields[]` (`id`, `label`, `kind`: text / date / period / statement, `value`, `personal`, `required`, `hint`, `sources`), `attachments[]`, `notes[]`. Pola `personal` (imiona, PESEL, adres, konto, podpis) są puste: wpisuje je użytkownik. Każda część planu rodzicielskiego ma własny wniosek (`parental-request-<k>`, `parental-father-request-<k>`). Źródła `rozp_wnioski` / `rozp_zasilki` — `ElementDetails` `Sources` musi je pokazywać (dziś pokazuje tylko Przewodnik/Załącznik i KP/ustawę).
  - **B.4 Terminy:** `Document.deadline` tylko tam, gdzie termin liczy Kodeks pracy; inaczej data na osi to dzień startu, nie termin.
  - **F23 Sprawdzenie wniosku:** `checkRequest({request, session_id?, phrase?})` → `RequestCheckResult` (`problems` z `severity`, `message`, `sources`, `element_id`). Wysyłaj pola formularza z ich `id` (`RequestField.id`), wtedy daty nie są zgadywane z etykiet. `phrase: true` = AI tylko przeredagowuje komunikaty.
  - **F24 Przetłumacz pismo z ZUS (AI):** `explainLetter(file, sessionId?)` → `LetterExplanation` (zawsze `ai: true`, `ai_label`): rodzaj pisma, co zrobić i do kiedy (daty przepisane z pisma), co przygotować, odwołanie, cytaty ze stronami, powiązane elementy osi. PDF/JPG/PNG, do 20 MB i 10 stron, nic nie zapisujemy.
  - **F8 Plany od celu:** `proposePlans(scenario, goal)` (`most-money` / `longest-home` / `equal-split` / `quick-return`) → do 3 planów z `figures` (dni urlopu, powrót do pracy, kwoty), `given_up`, `changed`; wybrany plan stosujesz przez `changeScenario(sessionId, plan.patch)`. `PLAN_GOAL_LABEL` w `lib/ui.ts`.
  - **F11 Test odporności:** `stressTest(scenario, timelines?)` → `events[]` z `verdict` (`loss` / `risk` / `kept`), `lines` (gotowe zdania), `assumed` (przyjęte daty), `money`, `periods`, `sensitive` (choroba albo śmierć mamy: pokazuj zwinięte). `patch` zdarzenia tylko do podglądu, nie do zapisu.
  - **F9 Zostawiacie na stole:** `Timeline.left_on_table: Leftover[]` (najbliższy termin pierwszy): `left-parental`, `left-parental-father`, `left-paternity`, `left-supplementary`, `left-parental-pool`, `left-rate-815` (`kind: "choice"`, `amount` = o ile więcej). Pusto po stracie dziecka albo śmierci mamy.
  - **F10 Punkty bez powrotu:** `Marker.irreversible: {lost, days_left, sources} | null` na `rate-815-deadline`, `paternity-deadline`, `parental-deadline` (kłódka z odliczaniem).
  - **F14 Nie przysługuje z dalszą drogą:** punkty wyjaśnienia `insurance-way`, `father-way`, `taken-in-way` (rodzaj `risk`) zaraz po punkcie o braku prawa.
  - **F37 Raport zgodności:** `GET /api/cases/agreement` → `CaseAgreement` (z pamięci odczytów, bez AI); każda różnica ma `reason` i `reason_text`. Typ miesiąca z Z-3 w sprawach to teraz `CasePayMonth`.
  - **B.10 Organizacje wsparcia:** żaden z materiałów ZUS ich nie wymienia (Poradnik: tylko kontakty ZUS i PIP). Listę robisz ze sprawdzonych stron organizacji.
  - Asystent ma narzędzia `propose_plans` i `stress_test` (tylko do odczytu) oraz zna punkty bez powrotu i „Zostawiacie na stole”.
- B.1 (kod): odczyt spraw daje `PayHistory` z miesięcy Z-3, podstawa z `base.py` krok po kroku; notatka o uproszczeniu usunięta. B.11 (kod): nowe pola odczytu i przełożenie na scenariusz (utrata pracy, ustalenia ZUS, zadłużenie, części, przejęcie, rodzina zastępcza).
- B.8 (F8, F9, F10, F11, F14), B.9 (F23, F24), B.3, B.4, B.10 — szczegóły wyżej i w CLAUDE.md.
- B.6 (22.11.2026): README od nowa: co potrafi aplikacja (wymagania a–j), lista funkcji z AI i bez AI (wymóg formalny), start, komendy, dane ZUS. Do uzupełnienia po scaleniu: tłumacz pism (F24) jako kolejna funkcja AI, adres demo.
- B.7 (22.11.2026): `PATCH /api/session/{id}/scenario` — body to obiekt z polami `Scenario` do zmiany (np. `{"parental_parts": [...]}`, `{"rate_815": true}`, `{"job_loss": {...}}`, `{"mother_pay_history": {...}}`; `null` czyści pole). Silnik waliduje jak po narzędziu czatu; odpowiedź to `SessionStart` (scenariusz, oś, następne pytanie). Błąd: 422 z polskim `detail` (np. „Nieznane pola scenariusza…”, „Nieprawidłowa wartość pola…”, komunikat silnika przy złym planie). Do historii czatu trafia ukryta notatka, co zmieniono, więc asystent tego nie dopytuje. Front: `changeScenario(sessionId, changes)` w `api.ts`, typ `ScenarioChanges` w `types.ts`. Testy: `backend/tests/test_scenario_patch.py`.
- Front (A, 22.11.2026): „Ile dostaniecie?”, ścieżka Pieniądze, karta Pieniądze ze wykresem schodkowym, „Dlaczego tyle?”, porównanie 100/70 a 81,5%, raport zgodności `/raport` (`GET /api/cases/report`), wniosek o urlop (wypełnienie, druk, wysyłka-atrapa), organizacje wsparcia.
- B.0 (22.11.2026): pytanie wywiadu dokleja serwer (`chat.py`), nie model; trafia też do historii modelu i do rozmowy po odświeżeniu. Front bez zmian: tekst odpowiedzi kończy się pytaniem, a szybkie odpowiedzi nadal idą po `question.key`. Test `test_the_interview_question_comes_from_the_code_not_the_model`, przypadek `premature-question-known-due-date` w `tools/eval`.
- Pełna podstawa wymiaru `engine/base.py` (B). Świadczenie rehabilitacyjne, pozostałe przypadki adopcji, kwoty za każdy okres, zasiłek po ustaniu ubezpieczenia, stawki w panelu admina (B, w `main`).
- Przykładowe sprawy: wybór, wgranie, odczyt przez AI, ubezpieczenie, porównanie z ZUS, „Pokaż na osi” (A).
