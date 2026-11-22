# Podział pracy i braki z zadania (stan 22.11.2026)

Dwa komputery, dwa agenty. Przed pracą `git pull`, po skończonym punkcie commit i `push`. Zrobiony punkt przenieś do „Zrobione” na dole albo usuń.

| | Komputer A (Wiktor, ta sesja) | Komputer B (drugi agent) |
|---|---|---|
| Zakres | **front**: `frontend/` | **logika**: `backend/` (silnik, wywiad, prompty, odczyt spraw), dane, wdrożenie |
| Gałąź | `ui/plan-redesign` | `main` albo własne gałęzie, scalane do `main` |

Granica: API i modele. Gdy B zmienia model albo endpoint, aktualizuje też `frontend/src/types.ts` (kopia modeli backendu) i pisze tu, co doszło. A nie zmienia logiki w `backend/`; gdy czegoś potrzebuje od backendu, dopisuje to niżej.

Źródło wymagań: `docs/Przewodnik_Rodzica_ZUS.pdf`, sekcje 3 („Oczekiwany rezultat”), 4 („Wymagania formalne”) i 6 („Sposób testowania”). Jury przetestuje demo na części przykładowych spraw i sprawdzi poprawność wyliczeń: „Strona powinna mieć możliwość uploadu/wyboru wybranych wniosków”.

## Komputer B — logika

### 1. Pełna podstawa wymiaru → podpiąć pod przykładowe sprawy
`engine/base.py` jest gotowy (Mikołaj, 22.11.2026: `Scenario.mother_pay_history` / `father_pay_history`, `PayHistory`, `Timeline.bases`). Zostało podpięcie odczytu spraw:
- `backend/app/cases/assess.py`, funkcja `monthly_pay`, dziś liczy zwykłą średnią i wpisuje `mother_pay`. Zamień to na `PayHistory(months=[engine PayMonth(month, amount, days_required, days_worked, …)], insured_from=…)` z `CaseFacts.pay`. Uwaga na nazwy: `app.cases.models.PayMonth` to inny model niż `app.engine.models.PayMonth`.
- Czytnik daje dziś `full_month` i `note`. Jeśli `base.py` potrzebuje dni wymaganych i przepracowanych oraz premii, dodaj te pola do `CaseFacts` (`cases/models.py`) i do instrukcji w `cases/reader.py`. Sprawy przeczytane wcześniej mają wtedy puste pola: przeczytaj je ponownie albo przyjmij domyślne.
- Gotowe, gdy: S80 (12 miesięcy z Z-3) pokazuje podstawę z `base.py` krok po kroku, a notatka o uproszczeniu znika.

### 2. Zgodność z decyzjami ZUS na 86 sprawach (cel „X/86” z CLAUDE.md)
- `cd backend && uv run python -m app.cases.batch --summary /tmp/sprawy.json` czyta sprawy, których nie ma w pamięci odczytów (`backend/.cases_cache/`, poza gitem), i wypisuje zgodność oraz listę różnic.
- Wynik z komputera A (22.11.2026, Gemini Pro): przeczytane 30 z 86 spraw. Wsad przerwał chwilowy limit Google (429 „temporarily rate-limited to prevent exceeding its monthly…”). Rozstrzygnięcie ZUS w aktach: przyznano 11, odmowa 8, częściowo 1, brak 10. **Zgodność: 15/20** tam, gdzie znane są obie strony. Oś powstała dla 19 spraw, kwoty dla 11. Różnice:
  - S08 (zlecenie, odmowa macierzyńskiego): kalkulator mówi „ubezpieczona”; sprawdzić dobrowolne chorobowe w odczycie i `insured_voluntarily`.
  - S09 (umowa pozorna, odmowa): ustalenie ZUS o niepodleganiu nie trafiło do okresu ubezpieczenia (`sickness: none`); poprawić instrukcję czytnika albo regułę.
  - S10 (zadłużenie, odmowa ojcowskiego): zadłużenie składkowe na dzień powstania prawa nie jest modelowane.
  - S19 (rodzina zastępcza, przyznano): kalkulator mówi „nieubezpieczona”; sprawdzić dzień powstania prawa przy przyjęciu dziecka (`right_day`, `taken_in_on`).
  - S21 (zasiłek w wysokości macierzyńskiego po likwidacji, przyznano): fakty nie są przekładane na `JobLoss` / zasiłek po ustaniu ubezpieczenia (`after_insurance.py`).
- Dalej: `uv run python -m app.cases.batch --jobs 1` doczyta pozostałe 56 spraw. Uwaga na miesięczny limit wydatków projektu Google: ten sam klucz obsługuje czat. `--only-cached` liczy samo podsumowanie, bez AI. Pamięć odczytów to dane z poufnych spraw: nie do gita. Żeby nie płacić drugi raz, można skopiować folder `.cases_cache` lokalnie (AirDrop, pendrive).
- Przejrzyj wiersze „różnica” i popraw przełożenie faktów na scenariusz w `backend/app/cases/assess.py`: utrata pracy w ciąży → `JobLoss`, dobrowolne chorobowe przy zleceniu i JDG, zadłużenie składkowe (S04), umowa „dla pozoru” (S07), części rodzicielskiego (S11), sprawy taty, adopcja. Sprawdzenie ubezpieczenia jest w `check_insurance`, porównanie z ZUS w `compare`.
- Gotowe, gdy: zgodność policzona na wszystkich sprawach z rozstrzygnięciem i każda różnica opisana (błąd odczytu, brak reguły albo inny powód odmowy).

### 3. Wnioski: dane do symulacji wypełnienia
Zadanie: „symulacji wypełnienia wniosków o urlopy i świadczenia związane z rodzicielstwem i ewentualnie przesłanie ich do pracodawcy/ZUS (wnioski o urlopy wymagają zaprojektowania, wnioski o świadczenia dostępne są na stronie www.zus.pl)”.
- Z materiałów (rozporządzenie z 11.03.2025 o wnioskach urlopowych; ZAM ze zus.pl) ustal pola każdego wniosku. Wypełnij je wartościami ze scenariusza i osi: kto, do kogo (pracodawca albo ZUS — `applications.py` już to wie), od kiedy, ile tygodni, podstawa prawna.
- Wystaw to przez API, np. `Document.form: {title, addressee, fields: [{label, value, source}]}` przy dokumentach osi albo `GET /api/session/{id}/forms`. Dopisz typy do `frontend/src/types.ts`.
- Front (A) zbuduje na tym widok formularza i atrapę „Wyślij”. Do tego czasu korzysta z `timeline.documents`.

### 4. Czat nie może wymyślać terminów
Test na Gemini: asystent napisał „wniosek o urlop macierzyński musisz złożyć do pracodawcy najpóźniej 21 lutego 2027”. W materiałach nie ma takiego terminu (CLAUDE.md, „Otwarte pytania”). Popraw `prompts.py` / `describe.py`, żeby terminy brał wyłącznie z `applications.py`. Dodaj przypadek do `tools/eval`.

### 5. Demo online (wymóg formalny)
Zadanie: „linki do demonstracji będącej stroną internetową; na stronie powinna być możliwość przetestowania wybranych załączonych przykładów (formularze w pdf)”.
- Hosting backendu (FastAPI) i frontendu (build Vite, `VITE_API_URL`), `CORS_ORIGINS`, klucze w zmiennych środowiska, migracje Supabase (`sessions`, `param_versions`).
- Na serwerze: folder ze sprawami (`CASES_DIR`, poza gitem) i skopiowana pamięć odczytów, żeby jury dostawało wyniki od razu.
- Gotowe, gdy: na publicznym adresie da się wybrać i wgrać sprawę, zobaczyć wynik i oś na telefonie i desktopie.

### 6. README i lista funkcji AI (wymóg formalny)
README jest nieaktualny („zrobiona jest faza 1”, „Claude przez OpenRouter”). Wymóg: „wskazanie, które z funkcjonalności działają ze wsparciem mechanizmów opartych na sztucznej inteligencji”.
- Funkcje AI: czat-wywiad i wyjaśnienia (Gemini Flash albo Claude) oraz odczyt spraw ze skanów (Gemini Pro albo Claude).
- Bez AI: silnik dat i kwot, sprawdzenie ubezpieczenia, porównanie z ZUS.

## Komputer A — front

1. Organizacje wsparcia (punkt i zadania): fundacje i stowarzyszenia przy śmierci dziecka, wcześniaku, poronieniu, ciężko chorym dziecku. Lista ze sprawdzonymi adresami i źródłem, w trybie łagodnym i w szczegółach takich sytuacji.
2. Symulacja wypełnienia i wysłania wniosków (widok na danych z punktu B.3).
3. Symulacja wniosku o odpis aktu urodzenia (gov.pl, rejestr stanu cywilnego).
4. „Co jeśli: Utrata pracy w ciąży” — dziś atrapa; podpiąć pod silnik przez czat jak pozostałe chipy.
5. Przykładowe sprawy: dopracować widok po wynikach wsadu (tytuły, statusy, różnice).
6. „Plany dla Was” czekają na drzewo decyzyjne.

## Konfiguracja na komputerze A (tylko `backend/.env`, nie w gicie)
`LLM_PROVIDER=google`, `LLM_MODEL=gemini-flash-latest` (czat), `CASES_MODEL=gemini-pro-latest` (sprawy), `GEMINI_API_KEY`, `CASES_DIR` (folder ze skanami). Klucz OpenRouter nie ma już środków.

## Zrobione
- B.0 (22.11.2026): pytanie wywiadu dokleja serwer (`chat.py`), nie model; trafia też do historii modelu i do rozmowy po odświeżeniu. Front bez zmian: tekst odpowiedzi kończy się pytaniem, a szybkie odpowiedzi nadal idą po `question.key`. Test `test_the_interview_question_comes_from_the_code_not_the_model`, przypadek `premature-question-known-due-date` w `tools/eval`.
- Pełna podstawa wymiaru `engine/base.py` (B). Świadczenie rehabilitacyjne, pozostałe przypadki adopcji, kwoty za każdy okres, zasiłek po ustaniu ubezpieczenia, stawki w panelu admina (B, w `main`).
- Przykładowe sprawy: wybór, wgranie, odczyt przez AI, ubezpieczenie, porównanie z ZUS, „Pokaż na osi” (A).
