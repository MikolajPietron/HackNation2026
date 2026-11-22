# Podział pracy i braki z zadania (stan 22.11.2026)

Dwa komputery, dwa agenty. Przed pracą `git pull`, po skończonym punkcie commit i `push`. Zrobiony punkt przenieś do „Zrobione” na dole albo usuń.

| | Komputer A (Wiktor, ta sesja) | Komputer B (drugi agent) |
|---|---|---|
| Zakres | **front**: `frontend/` | **logika**: `backend/` (silnik, wywiad, prompty, odczyt spraw), dane, wdrożenie |
| Gałąź | `ui/plan-redesign` | `main` albo własne gałęzie, scalane do `main` |

Granica: API i modele. Gdy B zmienia model albo endpoint, aktualizuje też `frontend/src/types.ts` (kopia modeli backendu) i pisze tu, co doszło. A nie zmienia logiki w `backend/`; gdy czegoś potrzebuje od backendu, dopisuje to niżej.

Źródło wymagań: `docs/Przewodnik_Rodzica_ZUS.pdf`, sekcje 3 („Oczekiwany rezultat”), 4 („Wymagania formalne”) i 6 („Sposób testowania”). Jury przetestuje demo na części przykładowych spraw i sprawdzi poprawność wyliczeń: „Strona powinna mieć możliwość uploadu/wyboru wybranych wniosków”.

## Komputer B — logika

Zostało (stan 22.11.2026, noc). Kolejność = priorytet. Front (A) ma już na planie wszystko, co B dał wcześniej (F6, F8–F11, F13, F14, F22–F24, B.3, B.4, B.7), więc nowe punkty niżej to następne funkcje z FUNKCJE.md, których front nie zrobi sam.

### 1. Demo online (wymóg formalny, blokuje oddanie) — B.5
- Jeden serwis: FastAPI serwuje zbudowany `frontend/dist` (fallback na `index.html` dla `/admin`, `/raport`), API pod `/api`. Dockerfile (uv + `npm run build`), zmienne z `.env.example`, hostowany Supabase na sesje i wersje parametrów, `CASES_MODEL` + klucz (tylko Claude albo Gemini, płatny). Hosting do ustalenia z Wiktorem (propozycja: Render albo Fly.io: jeden kontener, bez zimnego startu w czasie oceny).
- Po wdrożeniu: adres w README (B.6) i w CLAUDE.md.
- Decyzja (Mikołaj, 22.11.2026): na serwerze demo **nie ma skanów spraw**; jury wgrywa PDF samo, lista spraw pokazuje tylko numery i tematy. Dostawcę hostingu ustalimy później.

### 2. Zgodność z decyzjami ZUS na 86 sprawach (cel „X/86”) — wymaga płatnego odczytu
- Na komputerze A projekt Gemini jest przy limicie wydatków (429). Odczyt może iść z komputera B na jego kluczu (tylko Claude albo Gemini na płatnym koncie).
- Kod gotowy (B.1, B.11 w „Zrobione”): odczyt i przełożenie na scenariusz obsługują już utratę pracy, ustalenia ZUS („dla pozoru”, niepodleganie), zadłużenie, części rodzicielskiego, przejęcie urlopu i pełną podstawę z Z-3. Różnice mają kategorię (`reading` / `missing-rule` / `other-refusal`).
- Stare odczyty z `.cases_cache` nie mają nowych pól. Trzeba przeczytać ponownie co najmniej: S21 (`job_loss`), S08 i S09 (`zus_finding`, ostrzejsza reguła „voluntary”), S10 i S04 (`contribution_debt`), sprawy z niepełnymi miesiącami w Z-3 (dni), sprawy z premiami, przejęcie urlopu w sytuacji szczególnej (`mother_event`). S19 i S11 mogą działać już na starych odczytach.
- Potem: `uv run python -m app.cases.batch --jobs 1` (pozostałe 56 spraw i ponowny odczyt powyższych), `--only-cached` dla podsumowania; każdą różnicę opisać.

### 3. Kalendarz wypłat miesiąc po miesiącu (F4, P0) — B.12
- `Timeline.monthly`: dla każdego miesiąca kalendarzowego kwota mamy i taty i kto płaci (pracodawca albo ZUS), z silnika (1/30 dziennie, dni w miesiącu); `Timeline.money_total` (razem i na rodzica). Front nie sumuje kwot sam: dziś wykres w karcie Pieniądze ma słupek na okres, a F4 chce „ile wpływa w którym miesiącu, z dołkami”. Front przepnie wykres, gdy pola będą w `types.ts`.

### 4. Wniosek o łączenie urlopu rodzicielskiego z pracą (F6 + B.3) — B.13
- Edytor podziału (F13/F6) już zapisuje `work_fraction` w częściach, ale na osi nie ma wniosku o pracę w czasie urlopu. Dokument na część z pracą: formularz z rozporządzenia (§ 16), termin z KP art. 182¹ᵉ § 2 (21 dni przed podjęciem pracy), źródła. Front pokaże go sam (dokument z `form`).

### 5. Eksport terminów do kalendarza (F25) — B.14
- `GET /api/session/{id}/calendar.ics`: terminy wniosków (`Document.deadline`), punkty bez powrotu (`Marker.irreversible`), pierwsze dni urlopów; opis z regułą i źródłem. Bez danych osobowych. Front doda „Dodaj do kalendarza” w „Co przed Wami”.

### 6. Ochrona przed nadpisaniem planu — B.15
- `chat.py` wczytuje sesję na początku tury i na końcu zapisuje ją całą: zmiana przez `PATCH /scenario` w trakcie odpowiedzi asystenta (np. z drugiej karty) znika razem z ukrytą notatką. Front dziś blokuje zmiany, gdy asystent pisze. Backend: na końcu tury wczytaj sesję ponownie i dopisz historię do aktualnego scenariusza albo `409` dla `PATCH` w trakcie tury (wersja sesji).

### 7. Asystent i interfejs — B.16
- Prompt: rodzic może zmienić podział urlopu, stawkę i plan bez czatu (edytor, „Plany dla Was”); asystent ma się odwoływać do tych miejsc, a nie dopytywać o podział od zera. Po zmianie: `tools/eval` (koszt LLM, poza CI). README: tłumacz pism (F24) jako funkcja AI.

### Gdy zostanie czas (P2 z FUNKCJE.md)
- F38 Informacja zwrotna dla ZUS: `GET /api/admin/insights` — zanonimizowane liczby z tabeli `sessions` (na którym pytaniu wywiadu ludzie kończą, jakie zdarzenia, ile odmów, błędy silnika). Front doda zakładkę w `/admin`. Mocny argument „potencjał wdrożeniowy”.
- F40 Głos: `POST /api/tts` jako pośrednik do ElevenLabs (klucz tylko w `backend/.env`); front ma już miejsca: „Czytaj na głos” i mikrofon.
- F17 Wspólny plan pary: link dla drugiego rodzica do tej samej sesji (token tylko do odczytu albo do dopisania swoich danych).
- `api/cases.py` mógłby brać model przez `document_model.py` (dziś nie odrzuca modeli innych niż Claude i Gemini).

## Komputer A — front
Zrobione 22.11.2026 w nocy (szczegóły w „Zrobione”): wszystko, co B dał dla frontu (B.3, B.4, B.7, B.8, B.9). Dalej:

1. **Odpis aktu urodzenia (F35, wymóg zadania).** Atrapa przebiegu gov.pl.
2. **„Jedna rzecz na dziś” (F15).** Najbliższe zadanie z terminem na górze planu.
3. Gdy B da: wykres miesiąc po miesiącu (B.12), „Dodaj do kalendarza” (B.14), zakładka „Informacja zwrotna” w `/admin` (F38).
4. Przegląd całości na telefonie i desktopie, dostępność (F39: WCAG, kontrast, klawiatura).

## Konfiguracja na komputerze A (tylko `backend/.env`, nie w gicie)
`LLM_PROVIDER=google`, `LLM_MODEL=gemini-flash-latest` (czat), `CASES_MODEL=gemini-pro-latest` (sprawy), `GEMINI_API_KEY`, `CASES_DIR` (folder ze skanami). Klucz OpenRouter nie ma już środków.

## Zrobione
- Front (A, 22.11.2026 noc), gałąź `ui/plan-redesign`: zmiany planu bez czatu (`usePlanChange`: `PATCH /scenario`, pigułka „Cofnij” 5 s, Escape cofa; zablokowane, gdy asystent pisze); stawka 81,5% wybierana bezpośrednio; „Nie zostawiajcie tego na stole” (F9); kłódki z odliczaniem na osi, w liście i w szczegółach (F10); wniosek z `Document.form` (pola, załączniki, podstawa prawna, termin z `deadline`) i „Sprawdź wniosek” (F23, dane osobowe nie idą na serwer, przeredagowanie AI na życzenie); „Plany dla Was” z silnika (F8); „Co, jeśli coś pójdzie inaczej?” (F11, chip „Utrata pracy w ciąży” otwiera te zdarzenia); „Pismo z ZUS” (F24); edytor podziału urlopu rodzicielskiego z kafelkami tygodni i pracą do ½ etatu, podgląd z silnika (F13, F6, F3); źródła z rozporządzeń w szczegółach.
- Terminy ZAM osoby bez etatu (22.11.2026): nowe dokumenty osi `zam-supplementary`, `zam-parental`, `zam-parental-mother-<k>`, `zam-paternity`, `zam-parental-father`, `zam-parental-father-<k>` z `deadline` z rozporządzenia z 27.09.2026 (dzień przed startem zasiłku za ten okres; za uzupełniający dzień przed końcem zasiłku za urlop macierzyński). Źródło `rozp_zasilki` (§ 26, § 29, § 30 ust. 1, § 32 ust. 1, § 33 ust. 1). Główny ZAM (macierzyński) nadal bez terminu.
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
