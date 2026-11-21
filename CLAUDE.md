# CLAUDE.md — Zasiłkowy Przewodnik Przyszłego Rodzica

Projekt na HackNation 2026, wyzwanie ZUS. Opis wyzwania: `docs/Przewodnik_Rodzica_ZUS.pdf` (dalej: **Przewodnik**).

Stan na 21.11.2026: gotowy szkielet repo (FastAPI + React + Supabase), bez logiki aplikacji. Działa tylko `/api/health` i ekran-zaślepka.
Aktualizuj ten plik, gdy zmienia się struktura repo albo zapadają decyzje.

## Komendy (z katalogu głównego)

- `npm run setup` — instalacja: npm (frontend, CLI Supabase, concurrently) i `uv sync` (backend)
- `npm run dev` — FastAPI :8000 + Vite :5173 (Vite przekazuje `/api` do backendu)
- `npm test` — pytest; pojedynczy test: `cd backend && uv run pytest tests/test_x.py::test_y`
- `npm run lint` — ruff check + ruff format --check + oxlint + `tsc -b`; `npm run format` poprawia backend
- `npm run build` — build frontendu
- `npm run db:start` / `db:status` / `db:reset` / `db:migration <nazwa>` — lokalny Supabase (Docker)
- `npm run data:zus` — przygotowanie danych ZUS (patrz „Dane i poufność”)
- Backend sam: `cd backend && uv run …`; zależności: `uv add <pakiet>` (nie pip). Frontend: `npm install <pakiet> --workspace frontend`.

CI (`.github/workflows/ci.yml`) uruchamia to samo: backend (ruff, pytest) i frontend (oxlint, typecheck, build).

## Struktura repo

- `backend/` — Python 3.13, FastAPI, uv. `app/main.py` (aplikacja, CORS, `/api/health`), `app/config.py` (ustawienia z `.env`), `app/api/` (routery REST), `app/engine/` (silnik reguł), `app/services/` (Supabase, Claude), `tests/`.
- `frontend/` — React 19, TypeScript, Vite 8, Tailwind 4, Oxlint. `src/api.ts` (adres API z `VITE_API_URL`).
- `supabase/` — `config.toml`, `migrations/` (SQL), `seed.sql`.
- `tools/zus-data/` — pipeline danych ZUS (OCR, katalog spraw).
- `docs/` — Przewodnik; `docs/dokumentyZUS/` poufne, poza gitem.

## Core: oś czasu rodzica

Rodzi się dziecko (albo jest w drodze). Rodzice nie wiedzą, co im się należy. Aplikacja z ich sytuacji buduje
**osobistą oś czasu** i odpowiada na pytania:

1. Jakie świadczenie się należy i w jakich przypadkach — a kiedy **nie** należy?
2. Ile pieniędzy dostanie mama (i tata): stawka, kwota miesięczna, za jaki okres?
3. Ile wolnego może wziąć tata (ojcowski, jego 9 tygodni rodzicielskiego, przejęcie macierzyńskiego)?
4. Kto płaci (pracodawca czy ZUS), jaki wniosek złożyć, gdzie i do kiedy?
5. Jakie prawa ich chronią (zakaz zwolnienia, przedłużenie umowy)?
6. **Co się zmienia, gdy coś się wydarzy** (wcześniak, bliźnięta, hospitalizacja, martwe urodzenie, utrata pracy…)?

Oś czasu (to jest „zintegrowany kalkulator”, którego chce ZUS):
- Ścieżki: **Mama**, **Tata**, **Dziecko/zdarzenia**, **Pieniądze**, **Wnioski i terminy**.
- Odcinki: L4 w ciąży, macierzyński (przed/po porodzie), uzupełniający, rodzicielski (części), ojcowski, powrót do pracy, praca łączona z urlopem.
- Znaczniki: przewidywana data porodu, poród, terminy wniosków, koniec okna na 81,5% (21 dni po porodzie), koniec okna ojcowskiego (12. miesiąc życia), limit rodzicielskiego (31.12 roku 6. urodzin), okresy ochrony przed zwolnieniem.
- Każdy odcinek po kliknięciu: świadczenie, stawka, kwota, płatnik, wymagany wniosek/dokumenty, termin, **źródło z cytatem** (dokument + strona/artykuł).
- Przełączniki „Co jeśli…” (wcześniak, bliźnięta, szpital mamy, rezygnacja po 14 tyg., 81,5% zamiast 100/70…) — oś przelicza się, a zmiany są wyróżnione. To pokazuje interakcje i jest naszym wyróżnikiem.
- Mobile-first: oś pionowa na telefonie, pozioma na desktopie.

Funkcje wspierające (nie core): asystent Q&A z cytatami, wgranie/wybór przykładowej sprawy (wymóg testów jury), panel admina parametrów, atrapy integracji.

## Źródła wiedzy — hierarchia

1. **Przewodnik** — najważniejszy. Wyznacza zakres i reguły. Każda funkcja i reguła musi dać się powiązać z jego stroną.
2. **Załącznik** (`materialy/Załącznik_…docx`) — liczby: wymiary urlopów, stawki, podstawa wymiaru, limity 2026.
3. **Akty prawne** (`materialy/`): wyciąg z ustawy zasiłkowej, wyciąg z Kodeksu pracy, rozporządzenie z 27.09.2026 (dokumenty do zasiłków), rozporządzenie z 11.03.2025 (wnioski urlopowe) — podstawa prawna i cytaty.
4. **Poradnik ZUS 2026** (`materialy/`) — język prosty, kto jest ubezpieczony z jakiego tytułu (etat, zlecenie, JDG, zbiegi).
5. **Sprawy** (`sprawy/`) — tylko testy i demo uploadu.

Ścieżki `materialy/`, `sprawy/` są względem `docs/dokumentyZUS/`.
- Nie uzupełniaj przepisów wiedzą ogólną ani z internetu. Materiały są na stan 2026 i różnią się od starszych przepisów (np. ZUR, ZAO i Z-3b zlikwidowane 24.10.2026).
- Sprzeczność między źródłami albo luka → nie zgaduj, dopisz do „Otwarte pytania”.
- Uwaga: pdftotext spłaszcza indeksy górne w KP („Art. 1821a” = art. 182¹ᵃ). W UI pokazuj poprawną numerację.

## Ściąga domenowa (sprawdzona z materiałami 21.11.2026)

Liczby w kodzie biorą się wyłącznie z pliku parametrów; ta ściąga służy do orientacji.

| Świadczenie | Zasady | Stawka | Źródło |
|---|---|---|---|
| Wynagrodzenie chorobowe | Pierwsze 33 dni L4 w roku (14 dni od 50. r.ż.); płaci pracodawca | 100% w ciąży (poza ciążą 80%) | Przewodnik s.3–4; KP art. 92 |
| Zasiłek chorobowy w ciąży | e-ZLA z kodem „B”; prawo po 30 dniach ubezpieczenia obowiązkowego / 90 dniach dobrowolnego (zlecenie, JDG); nie-pracownik od 1. dnia; max 270 dni, także po ustaniu ubezpieczenia | 100% (bez „B”: 80%) | Przewodnik s.3–4; ustawa art. 4, 8, 11 |
| Zasiłek w wysokości zasiłku macierzyńskiego | Utrata pracy w ciąży: upadłość, likwidacja, śmierć pracodawcy albo bezprawne rozwiązanie umowy (wyrok); wypłacany do porodu | 100% | Przewodnik s.4 |
| Macierzyński | 20/31/33/35/37 tyg. przy 1/2/3/4/5+ dzieciach; ≤6 tyg. przed przewidywaną datą porodu, reszta po porodzie; 14 tyg. po porodzie mama wykorzystuje osobiście; tydzień = 7 dni kalendarzowych | 100% | Przewodnik s.5; KP art. 180, 183¹; Załącznik |
| Uzupełniający | Wcześniak albo dziecko w szpitalu; tydzień za tydzień szpitala (niepełny w górę), max 8 albo 15 tyg. wg tabeli (tydzień ciąży, masa ≤1000 g, hospitalizacja); jednorazowo, bezpośrednio po macierzyńskim, jedno z rodziców | 100% | Przewodnik s.8; Załącznik; KP art. 180² |
| Rodzicielski | 41/43 tyg. (1/2+ dzieci), z „Za życiem” 65/67; po 9 tyg. nieprzenoszalne dla każdego rodzica; max 5 części do 31.12 roku, w którym dziecko kończy 6 lat; rodzice równocześnie lub naprzemiennie | 70% | Przewodnik s.5–7; KP art. 182¹ᵃ, 182¹ᶜ; Załącznik |
| Ojcowski | 14 dni: 1×14 albo 2 części ≥7 dni; do 12. miesiąca życia (adopcja: 12 mies. od uprawomocnienia, max do 14 r.ż.); liczba dzieci nie wydłuża | 100% | Przewodnik s.8; KP art. 182³ |
| Na warunkach macierzyńskiego | Adopcja, rodzina zastępcza niezawodowa; wymiar jak macierzyński, min. 9 tyg.; dziecko do 7 lat (10 przy odroczeniu obowiązku szkolnego), przy przysposobieniu do 14 lat | 100% | Przewodnik s.8–9; Załącznik |
| Wariant 81,5% | Wniosek mamy ≤21 dni po porodzie: 81,5% za cały macierzyński + rodzicielski, poza 9 tyg. drugiego rodzica (70%) | 81,5% | Przewodnik s.9; ustawa art. 30a, 31 |
| Minimum | Zasiłek macierzyński netto (po zaliczce PIT) < świadczenie rodzicielskie → podwyższenie do 1 000 zł/mies. | — | ustawa art. 31 ust. 3a; kwota tylko w pismach ZUS w sprawach |

**Podstawa wymiaru** (Załącznik):
- Pracownik: średnia z 12 pełnych miesięcy kalendarzowych przed miesiącem powstania prawa, pomniejszona o 13,71%. Krótsze zatrudnienie: liczy się z pełnych miesięcy, a w 1.–2. miesiącu pracy z wynagrodzenia z umowy. Miesiąc przepracowany w mniej niż połowie pomija się, w co najmniej połowie uzupełnia. Premie kwartalne i roczne wchodzą jako 1/12.
- Nie-pracownik: zadeklarowana podstawa składek z 12 miesięcy minus 13,71%. Limit podstawy zasiłku 2026: 20 321,30 zł.
- Przerwa między zasiłkami krótsza niż miesiąc → podstawa się nie zmienia.
- Kwota dzienna: 1/30 miesięcznej (założenie z ustawy art. 11 ust. 5 — do potwierdzenia).

**Kto płaci** (Przewodnik s.1 przypis 1, s.3):
- Wynagrodzenie chorobowe płaci pracodawca.
- Zasiłki wypłaca płatnik składek, jeśli zgłasza do ubezpieczenia chorobowego ponad 20 osób (stan na 30.11 poprzedniego roku). W pozostałych przypadkach, w tym przy JDG, wypłaca ZUS.
- Pieniądze zawsze pochodzą z FUS.

**Wnioski** (Przewodnik s.3, 6, 12):
- e-ZLA trafia do ZUS i pracodawcy automatycznie.
- Pracownica składa wniosek o urlop u pracodawcy. Ten wypłaca albo przekazuje Z-3 (ZAS-12 na dalszy okres) do ZUS.
- Zlecenie: ZAM do płatnika albo ZUS, płatnik dołącza Z-3a.
- JDG: ZAS-53 (chorobowy) albo ZAM (macierzyński) do ZUS.
- Od 24.10.2026 ZUR i ZAO są połączone z ZAM, a Z-3b zlikwidowany. W starszych sprawach nadal występują — rozpoznawaj je.

**Terminy**:
- Uzupełniający: wniosek ≥21 dni przed końcem macierzyńskiego.
- Rodzicielski: ≥21 dni przed startem.
- Łączenie z pracą: ≥21 dni przed podjęciem pracy.
- Rezygnacja mamy z reszty macierzyńskiego: ≥7 dni przed powrotem.
- Ojcowski: ≥7 dni przed.
- 81,5%: ≤21 dni po porodzie.

Źródła: KP art. 180, 180², 182¹ᵈ, 182¹ᵉ, 182³; ustawa art. 30a.

**Prawa** (Przewodnik s.10; KP art. 177):
- Okres ochrony: ciąża, urlopy rodzicielskie wszystkich rodzajów oraz czas od złożenia wniosku o urlop. Ochrona zaczyna się najwcześniej 14 dni przed częścią macierzyńskiego, 21 dni przed uzupełniającym lub rodzicielskim i 7 dni przed ojcowskim.
- W tym czasie pracodawca nie może wypowiedzieć ani rozwiązać umowy ani się do tego przygotowywać. Wyjątek: wina pracownika i zgoda związku zawodowego.
- Umowa terminowa albo próbna dłuższa niż miesiąc, która skończyłaby się po 3. miesiącu ciąży, przedłuża się do dnia porodu.
- Ochrona nie dotyczy zlecenia ani JDG.

**Zagrożenia** (Przewodnik s.9–10 + sprawy):
- umowa albo JDG zawarta „dla pozoru” (S07),
- podwyższenie podstawy składek w ciąży,
- brak ubezpieczenia chorobowego w dniu porodu, np. niezgłoszenie do dobrowolnego albo koniec pracy, zlecenia lub JDG przed porodem (S01, S02, S03, S08),
- zadłużenie składkowe osoby z JDG lub osoby współpracującej (S04, S05, S10),
- 6. część rodzicielskiego (S11).

## Interakcje — reguły modyfikujące oś (serce silnika)

Każda interakcja = osobna reguła ze źródłem i testem. W nawiasach: sprawy testowe z katalogu.

1. **Poród a urlop przed porodem**: część macierzyńskiego niewykorzystana przed porodem przechodzi na czas po porodzie. Bez urlopu przed porodem start = dzień porodu. (KP 180 §3, 183¹; S80)
2. **Wcześniak / dziecko w szpitalu**: dochodzi uzupełniający bezpośrednio po macierzyńskim, więc rodzicielski i powrót do pracy się przesuwają. Po 8 tyg. macierzyńskiego mama może odłożyć resztę do wyjścia dziecka ze szpitala. (Przewodnik s.8; KP 180², 181; S25, S30, S27)
3. **Wieloraczki**: dłuższy macierzyński (31–37) i rodzicielski (43). Ojcowski bez zmian. Uzupełniający liczony wg najniższej masy i najdłuższej hospitalizacji. (Załącznik; S27, S16)
4. **„Za życiem”**: rodzicielski 65/67 tyg. (Załącznik; S32, S16)
5. **Martwe urodzenie / zgon dziecka**: przed 8. tygodniem życia macierzyński trwa 8 tyg. po porodzie, ale nie krócej niż 7 dni od zgonu; przy wieloraczkach liczy się według żyjących dzieci. Zgon po 8 tyg. → 7 dni od zgonu. UI w delikatnym tonie, z organizacjami wsparcia. (Przewodnik s.6; KP 180¹; S12, S16)
6. **Tata przejmuje macierzyński**: gdy mama rezygnuje po 14 tyg., tata bierze resztę od następnego dnia. Wcześniej, już po 8 tyg., gdy mama jest w szpitalu, ma orzeczenie o niezdolności do samodzielnej egzystencji albo porzuciła dziecko. Gdy mama zmarła — od dnia po zgonie, bez minimum 8 tyg. (Przewodnik s.7; KP 180 §4–13; S37, S39)
7. **Mama nieubezpieczona**: tata ma zasiłek za rodzicielski i ojcowski. Ojcowski przysługuje też tacie, który zaczął pracę po narodzinach (dziecko < 12 mies.). (Przewodnik s.7–8; S38)
8. **Utrata pracy w ciąży** (upadłość, likwidacja, śmierć pracodawcy, bezprawne zwolnienie): zasiłek w wysokości macierzyńskiego do porodu, potem macierzyński po ustaniu ubezpieczenia. (Przewodnik s.4; ustawa art. 30; S23)
9. **Umowa terminowa w ciąży**: przedłużona do porodu, potem macierzyński po ustaniu ubezpieczenia. (Przewodnik s.10; ustawa art. 30; S84)
10. **L4 w ciąży → macierzyński bez przerwy**: ta sama podstawa wymiaru (przerwa < 1 mies.). (Załącznik)
11. **Łączenie rodzicielskiego z pracą** (≤ pół etatu): rodzicielski wydłuża się proporcjonalnie, zasiłek przysługuje za wydłużony okres. (Przewodnik s.9; KP 182¹ᵉ–182¹ᶠ; S34, S16)
12. **81,5% zamiast 100%/70%**: jedna stawka na macierzyński i rodzicielski mamy; 9 tyg. drugiego rodzica zawsze 70%. Okno na wybór: 21 dni po porodzie. (ustawa art. 30a, 31)
13. **Części rodzicielskiego**: każda liczy się do limitu 5; ostatnia musi skończyć się do 31.12 roku 6. urodzin. (KP 182¹ᶜ; S11)
14. **JDG po macierzyńskim**: trzeba ponownie zgłosić się do dobrowolnego chorobowego. Przerwa bez ubezpieczenia przed rodzicielskim oznacza odmowę. (sprawa S03; Poradnik — zbieg z zasiłkiem macierzyńskim)

## Architektura (docelowa)

- **Podział**: frontend (React) woła wyłącznie nasze REST API pod `/api/*` (FastAPI). Z Supabase łączy się tylko backend, kluczem sekretnym z `backend/.env`. Frontend nie ma kluczy Supabase.
- **Silnik** (`backend/app/engine/`): czysty i deterministyczny Python, bez I/O, bez bazy i bez LLM. Modele Pydantic: wejście `Scenario` (rodzice, tytuły ubezpieczenia i daty, zarobki, data porodu, liczba dzieci, zdarzenia, wybory użytkownika), wyjście `Timeline` (`segments`, `markers`, `applications`, `warnings`, `rights`). Każdy element ma `sources: list[SourceRef]` (`doc`, `page`, `article`, `quote`). Reguły bazowe budują oś, a interakcje nakładają się po nich w jawnej kolejności. Te same modele służą za schemat API (frontend dostaje gotowe odcinki do narysowania).
- **Parametry**: wszystkie liczby (tygodnie, stawki, limity, kwoty), każda z odnośnikiem do źródła. Wersja bazowa w pliku JSON w repo (np. `backend/params/2026.json`). Panel admina zapisuje zmiany jako nowe wersje w tabeli Supabase. Silnik dostaje parametry jako argument i sam nie czyta bazy. Bez magicznych liczb w kodzie.
- **Baza**: schemat wyłącznie przez migracje SQL (`npm run db:migration <nazwa>` → `supabase/migrations/`), bez ORM-owych migracji. RLS włączone na każdej tabeli.
- **Daty**: `datetime.date`, tydzień = `timedelta(days=7)` (7 dni kalendarzowych), przedziały liczone włącznie, „dziś” w strefie Europe/Warsaw (`zoneinfo`).
- **LLM**: Claude przez pakiet `anthropic` (Python SDK), model z `LLM_MODEL` w `.env` (domyślnie `claude-opus-5-5`). Używany tylko do trzech rzeczy:
  - asystent Q&A z cytatami — Claude citations na PDF-ach materiałów zwracają dosłowny `cited_text` i numer strony; nie łączyć z `output_config.format`, bo API zwraca 400,
  - odczyt sprawy ze skanu (vision) do postaci `Scenario`, z numerami stron,
  - objaśnienia słowne.

  **Nigdy nie liczy kwot ani dat.** Każda funkcja AI jest oznaczona w UI (wymóg wyzwania).
- **Atrapy** (bez prawdziwych integracji): mObywatel, dane z ZUS, zadłużenie składkowe, e-ZLA, PUE/eZUS, wypełnianie i wysyłka wniosków, odpis aktu urodzenia, organizacje wsparcia, linki zus.pl / gov.pl / PIP.

## Dane i poufność — twarde zasady

- `docs/dokumentyZUS/` jest w `.gitignore`. Dokumenty ZUS są „wyłącznie na użytek HackNation”: nie commituj ich, nie wklejaj treści do commitów, issue ani PR i nie kopiuj do `public/`.
- Nazwy plików spraw zawierają imiona. W UI, logach i testach używaj ID `S01–S86` z katalogu.
- Nie wysyłaj skanów spraw do zewnętrznych API, dopóki mentorzy ZUS tego nie potwierdzą. Hostowany Supabase to też zewnętrzna usługa: danych ze spraw nie trzymamy w nim ani w `seed.sql`. Lokalny Supabase w Dockerze jest OK.
- Sprawy to skany bez warstwy tekstowej: odręczne daty, obrócone strony, ok. 15% stron pustych. OCR (tesseract) służy tylko do wyszukiwania i kategorii — **nie do liczb**, bo myli cyfry. Liczby czyta model z obrazu strony.
- Pipeline: `tools/zus-data/run.sh` → `docs/dokumentyZUS/{materialy,sprawy,ocr,katalog_spraw.md,katalog_spraw.json}`. Duplikat „Dariusz Go_3 … (1)” jest pomijany.

## Testy

- Jednostkowe dla każdej reguły i interakcji: przykłady z Przewodnika i liczby z Załącznika.
- Regresja na sprawach: `katalog_spraw.json` to klucz rozstrzygnięć (przyznano/odmowa, wykryte z OCR w 60/86 — resztę zweryfikować wzrokowo). W sprawach nie ma kwot: kwoty liczymy z tabeli Z-3 i pokazujemy wyliczenie krok po kroku.
- Cel na prezentację: „zgodność z decyzjami ZUS: X/86”.

## Wymagania wyzwania (checklista)

- Demo online: wgranie lub wybór przykładowej sprawy, sprawdzenie ubezpieczenia i wyliczeń.
- RWD (telefon + desktop), prezentacja ≤10 slajdów, film ≤3 min, repo, wskazanie funkcji opartych na AI.
- Kalkulatory a–j z Przewodnika (s.12–13) w jednym zintegrowanym kalkulatorze — u nas to oś czasu.
- Panel admina do parametrów (zmiany przepisów).
- Ocena: związek z wyzwaniem 25%, kompletność + UX 25%, pomysł 20%, oryginalność 15%, potencjał wdrożeniowy 15%.

## Otwarte pytania do mentorów ZUS

- Minimalna podstawa wymiaru 2026: w Załączniku brak tabeli. Nasze wyliczenie: 4 806 × (1 − 13,71%) ≈ 4 147,10 zł.
- Minimum 1 000 zł: jak liczyć zaliczkę PIT przy porównaniu netto?
- Czy stawka dzienna 1/30 dotyczy też zasiłku macierzyńskiego?
- Czy skany spraw wolno wysyłać do zewnętrznego API AI?

## Konwencje

- UI i treści po polsku. Kod, identyfikatory i commity po angielsku.
- Python: ruff (linia 100), adnotacje typów wszędzie, modele Pydantic na granicy API. TypeScript: oxlint + `tsc -b`, komponenty funkcyjne, style w Tailwind.
- Sekrety tylko w `backend/.env` i `frontend/.env.local` (oba w `.gitignore`). Nowa zmienna = wpis w odpowiednim `.env.example`.
- Nowa reguła = źródło (dokument + strona albo artykuł) + test. Bez źródła nie wchodzi.
- Język odpowiedzi dla rodzica: prosty, konkretny („dostaniesz”, „złóż do”), z odnośnikiem do źródła. Przy trudnych sytuacjach — empatycznie.
