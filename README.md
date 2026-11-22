# Zasiłkowy Przewodnik Przyszłego Rodzica

Projekt na HackNation 2026, wyzwanie ZUS. Aplikacja buduje rodzicom osobistą **oś czasu** od ciąży do powrotu do pracy: jakie świadczenia im przysługują (i kiedy nie), ile pieniędzy dostaną, kto płaci, jakie wnioski złożyć, gdzie i do kiedy, jakie prawa ich chronią. Po każdej zmianie sytuacji (wcześniak, bliźnięta, utrata pracy, przejęcie urlopu przez tatę…) oś przelicza się, a zmiany są podświetlone.

Każda reguła ma dosłowny cytat ze źródła: Przewodnika ZUS (opis wyzwania), Kodeksu pracy, ustawy zasiłkowej albo Załącznika ZUS. Produkt, domena i zasady pracy: [CLAUDE.md](CLAUDE.md). Plan funkcji: [FUNKCJE.md](FUNKCJE.md). Podział bieżącej pracy: [ZADANIA.md](ZADANIA.md).

## Demo online

https://przewodnik-rodzica.up.railway.app (Railway, jeden kontener: FastAPI serwuje też zbudowany front; `Dockerfile`, `railway.json`). Panel parametrów: `/admin`, raport zgodności: `/raport`. Rozmowy są w pamięci serwera. Skanów spraw ZUS na serwerze nie ma: sprawę wgrywa się samemu albo wybiera przykładową rodzinę.

Wdrożenie nowej wersji: `npx @railway/cli up --service app` z katalogu głównego (po `railway login`).

## Co potrafi

| Wymaganie z wyzwania | W aplikacji |
|---|---|
| a) świadczenia w ciąży, także brak prawa | L4 w ciąży (wynagrodzenie chorobowe i zasiłek chorobowy 100%), świadczenie rehabilitacyjne, zasiłek w wysokości zasiłku macierzyńskiego po utracie pracy, zasiłek po ustaniu ubezpieczenia; brak ubezpieczenia jako „Uwaga” z wyjaśnieniem |
| b) zasiłek macierzyński dla obojga rodziców | okresy i kwoty dla mamy i taty: macierzyński (20–37 tyg.), uzupełniający, rodzicielski, ojcowski, przejęcie urlopu, „Za życiem”, wcześniak i szpital, martwe urodzenie i zgon dziecka |
| c) łączenie urlopu rodzicielskiego z pracą | plan części urlopu z pracą do pół etatu: wydłużenie urlopu i mniejszy zasiłek w tygodniach pracy |
| d) oboje rodzice | podział puli urlopu rodzicielskiego, części jednocześnie albo po kolei, 9 tygodni każdego rodzica, 100/70% albo 81,5% |
| e), j) adopcja i rodzina zastępcza | urlop na warunkach urlopu macierzyńskiego, granice wieku dziecka, rodzicielski, ojcowski przy adopcji, przekazanie urlopu, adopcja po rodzinie zastępczej |
| f) indywidualna podstawa wymiaru | pełna podstawa z miesięcy z zaświadczenia płatnika (Z-3, Z-3a): krótsze ubezpieczenie, miesiące przepracowane w części, premie, minimalna podstawa, górna granica; wybór albo wgranie przykładowej sprawy |
| g) dokumenty, terminy, gdzie złożyć | wnioski na osi z terminami z Kodeksu pracy, kto wypłaca (pracodawca powyżej 20 ubezpieczonych albo ZUS), ZAM, Z-3, Z-3a, ZAS-53, e-ZLA |
| h) zagrożenia | umowa „dla pozoru”, podwyższenie podstawy w ciąży, brak ubezpieczenia w dniu porodu, szczególna ochrona przed zwolnieniem |
| zintegrowany kalkulator | jedna oś dla wszystkich przypadków; „Co jeśli…” przelicza ją od razu; kalkulator bez AI: `POST /api/timeline` |
| panel administracyjny | `/admin`: wymiary urlopów, stawki 100/70/81,5%, terminy wniosków; wersje od daty obowiązywania z podglądem skutków |
| symulacje | logowanie mObywatel, dane z ZUS, zadłużenie składkowe, e-ZLA, PUE/eZUS — oznaczone w interfejsie jako atrapy z danymi przykładowymi |

## Gdzie działa sztuczna inteligencja

Wymóg wyzwania: „wskazanie, które z funkcjonalności działają ze wsparciem mechanizmów opartych na sztucznej inteligencji”. W interfejsie każda funkcja AI ma oznaczenie „AI”.

**Z AI:**
- **Czat-wywiad i wyjaśnienia** (Pydantic AI; Gemini Flash albo Claude): zapisuje odpowiedzi rodzica narzędziami, które zmieniają scenariusz, i tłumaczy oś prostym językiem, cytując źródła. Pytania wywiadu i ich kolejność wyznacza kod, nie model.
- **Odczyt przykładowych spraw ze skanów** (model z obsługą obrazu; Gemini Pro albo Claude): wyciąga fakty (zatrudnienie, okresy ubezpieczenia, zarobki z Z-3, decyzję ZUS) z numerami stron. Rodzic albo juror może je poprawić przed liczeniem.
- **„Przetłumacz pismo z ZUS”** (Gemini Pro albo Claude): ze zdjęcia albo PDF pisma mówi prostym językiem, co to za pismo, co zrobić i do kiedy; daty tylko przepisane z pisma, bez danych osobowych, nic nie jest zapisywane.
- **Sprawdzenie wniosku przed złożeniem**: reguły bez AI (brakujące pola, daty, terminy, załączniki, formularze zlikwidowane 24.10.2026); AI może na życzenie tylko przeredagować komunikaty.
- **Ilustracje** w interfejsie wygenerowano modelem obrazów (`tools/illustrations/`); w działającej aplikacji to zwykłe pliki.

**Bez AI (deterministyczny silnik reguł):** wszystkie daty i kwoty, prawo do zasiłku, podstawa wymiaru, wnioski z formularzami i terminy, plany od celu i test odporności planu, „Zostawiacie na stole”, punkty bez powrotu, sprawdzenie ubezpieczenia w sprawie i porównanie z decyzją ZUS, panel parametrów. AI nigdy nie liczy kwot ani dat i nie ustala prawa do zasiłku.

## Stack

- **Backend**: Python 3.13, FastAPI, uv, Pydantic — `backend/` (silnik reguł w `app/engine/` bez I/O i bez AI)
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS 4, Motion, komponenty Spectrum UI, kolory ZUS — `frontend/`
- **Baza**: Supabase (Postgres) — rozmowy (`sessions`) i wersje parametrów (`param_versions`); migracje SQL w `supabase/migrations/`. Bez Supabase dane są w pamięci procesu.
- **AI**: Pydantic AI; dostawca z `LLM_PROVIDER` (`google`, `anthropic` albo `openrouter`), model spraw z `CASES_MODEL`

## Wymagania

- Node.js 24 (minimum 20.19) i npm
- [uv](https://docs.astral.sh/uv/) — sam pobierze Pythona 3.13
- Docker — tylko do lokalnej bazy Supabase

## Start

```bash
npm run setup                          # zależności: frontend, CLI Supabase, backend
cp backend/.env.example backend/.env   # uzupełnij klucz modelu (np. GEMINI_API_KEY) i CASES_DIR
npm run dev                            # API na :8000 + frontend na :5173
```

Otwórz http://localhost:5173: onboarding zbiera kilka faktów (kim jesteś, data porodu albo urodzenia, praca), potem pojawia się oś i czat. Bez klucza modelu czat zwraca komunikat o wyłączonym asystencie, a oś i kalkulator działają dalej. Dokumentacja API: http://localhost:8000/docs.

Cytaty z Załącznika ZUS sprawdzane są lokalnie: `python3 tools/przewodnik/extract_zalacznik.py` tworzy `backend/app/assistant/zalacznik.json` z materiałów (plik poza gitem).

## Komendy

| Komenda | Co robi |
|---|---|
| `npm run dev` | backend (FastAPI, :8000) i frontend (Vite, :5173) naraz |
| `npm run dev:api`, `npm run dev:web` | to samo osobno |
| `npm test` | testy backendu (pytest): reguły z ręcznie policzonymi datami i kwotami, dosłowność cytatów, API na skryptowanym modelu |
| `npm run lint` | ruff, oxlint i sprawdzenie typów TypeScript |
| `npm run format` | formatowanie backendu (ruff) |
| `npm run build` | build frontendu |
| `npm run db:start`, `db:stop`, `db:status` | lokalny Supabase w Dockerze |
| `npm run db:migration <nazwa>` | nowa migracja SQL |
| `npm run db:reset` | odtworzenie lokalnej bazy z migracji i `seed.sql` |
| `npm run data:zus` | przygotowanie danych ZUS: OCR i katalog spraw (macOS, tesseract, poppler) |
| `cd backend && uv run python -m app.cases.batch --only-cached` | zgodność z decyzjami ZUS na przeczytanych sprawach, bez AI |
| `cd backend && uv run python ../tools/eval/run.py` | test prawdziwego modelu na scenariuszach, na osobnym backendzie :8010 (kosztuje wywołania; instrukcja w `tools/eval/README.md`) |

## Struktura

```
backend/         FastAPI: app/api (REST), app/engine (silnik reguł), app/assistant (czat),
                 app/cases (przykładowe sprawy), app/services, params/2026.json, tests/
frontend/        React + Vite + Tailwind: onboarding, ekran planu z osią, czat, panel /admin
supabase/        config.toml, migrations/, seed.sql
tools/           przewodnik/ (tekst źródeł do cytowania), eval/ (test modelu), zus-data/ (OCR spraw),
                 illustrations/ (generator ikon)
docs/            opis wyzwania (Przewodnik_Rodzica_ZUS.pdf); dokumentyZUS/ jest poufne i poza gitem
```

## Dane od ZUS

Materiały i przykładowe sprawy od ZUS trzymamy lokalnie w `docs/dokumentyZUS/` (katalog jest w `.gitignore`). Nie wolno ich kopiować ani rozpowszechniać i nie trafiają do repozytorium. Skany spraw czyta wyłącznie Claude albo Gemini (płatny klucz, decyzja zespołu z 22.11.2026); odczytane fakty leżą tylko w `backend/.cases_cache/`, poza gitem. Szczegóły: CLAUDE.md, „Dane i poufność”.
