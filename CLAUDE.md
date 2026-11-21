# CLAUDE.md — Zasiłkowy Przewodnik Przyszłego Rodzica

Projekt na HackNation 2026, wyzwanie ZUS. Opis wyzwania: `docs/Przewodnik_Rodzica_ZUS.pdf` (dalej: **Przewodnik**).

Stan na 21.11.2026: budujemy fazami, po jednym punkcie Przewodnika naraz (patrz „Fazy”). Zrobione: faza 1 „Przygotowanie do porodu” i cała faza 2 „Urodzenie dziecka” (prawo ubezpieczonej mamy do zasiłku, wymiar urlopu macierzyńskiego i 14 tygodni, uzupełniający urlop macierzyński, urlop rodzicielski, „Za życiem”). Onboarding zbiera rolę, czy dziecko już jest, liczbę dzieci, datę, pracę i zarobki; wszystko zapisuje się w sesji (Supabase). Wywiad w czacie zbiera resztę, silnik liczy oś, frontend ją rysuje.
Aktualizuj ten plik, gdy zmienia się struktura repo albo zapadają decyzje.

## Komendy (z katalogu głównego)

- `npm run setup` — instalacja: npm (frontend, CLI Supabase, concurrently) i `uv sync` (backend)
- `npm run dev` — FastAPI :8000 + Vite :5173 (Vite przekazuje `/api` do backendu)
- `npm test` — pytest; pojedynczy test: `cd backend && uv run pytest tests/test_x.py::test_y`
- `npm run lint` — ruff check + ruff format --check + oxlint + `tsc -b`; `npm run format` poprawia backend
- `npm run build` — build frontendu
- `npm run db:start` / `db:status` / `db:reset` / `db:migration <nazwa>` — lokalny Supabase (Docker)
- `npm run data:zus` — przygotowanie danych ZUS (patrz „Dane i poufność”)
- `python3 tools/przewodnik/extract_pages.py` — po zmianie PDF Przewodnika odświeża `backend/app/assistant/przewodnik_pages.json` (tekst stron, z którego wycinamy sekcje)
- `python3 tools/przewodnik/extract_kp.py` — odświeża `backend/app/assistant/kodeks_pracy.json`: przepisy Kodeksu pracy, które cytujemy (lista w skrypcie; źródłem jest wyciąg z materiałów ZUS). Skrypt przywraca tylko sklejone „nie” („niewięcej”) i indeksy górne w numerach artykułów („art. 1831 § 1” → „art. 183¹ § 1”)
- Backend sam: `cd backend && uv run …`; zależności: `uv add <pakiet>` (nie pip). Frontend: `npm install <pakiet> --workspace frontend`.

CI (`.github/workflows/ci.yml`) uruchamia to samo: backend (ruff, pytest) i frontend (oxlint, typecheck, build).

## Struktura repo

- `backend/` — Python 3.13, FastAPI, uv.
  - `app/main.py` — aplikacja, CORS, `/api/health`; `app/config.py` — ustawienia z `.env`; `app/clock.py` — „dziś” w Europe/Warsaw.
  - `app/api/` — routery: `chat.py` (`POST /api/chat`, strumień NDJSON), `session.py` (`PUT /api/session/{id}/onboarding`: zapis odpowiedzi z onboardingu; `GET`/`DELETE /api/session/{id}`: przywrócenie i usunięcie rozmowy), `timeline.py` (`POST /api/timeline`, kalkulator bez AI), `deps.py` (zależności: model, parametry, dziś, magazyn sesji; testy je podmieniają).
  - `app/engine/` — silnik: `models.py` (`Scenario`, `Timeline` z odcinkami, ważnymi dniami i dokumentami, `SourceRef`), `params.py` (model parametrów), `timeline.py` (reguły zrobionych faz, `changed_element_ids`), `insurance.py` (czy mama jest ubezpieczona: `coverage`), `supplementary.py` (wymiar uzupełniającego urlopu macierzyńskiego z pobytów w szpitalu), `parental.py` (wymiar i ostatni dzień urlopu rodzicielskiego), `explain.py` (wyjaśnienie przypadku: `Timeline.notes`, `changed_note_ids`), `wording.py` (daty słownie, liczba dzieci), `plausibility.py` (sprawdzenie, czy wpisana data ma sens: literówki w roku itp.).
  - `app/assistant/` — agent Pydantic AI (`agent.py`: narzędzia i zdarzenia), `guide.py` (sekcje Przewodnika wycinane z `przewodnik_pages.json`; sekcja może mieć części na dwóch stronach, gdy zdanie przechodzi przez łamanie strony, a `pages_of` podaje strony cytatu), `law.py` i `kodeks_pracy.json` (cytowane przepisy Kodeksu pracy), `prompts.py` (instrukcje po polsku z dosłownym tekstem źródeł i planem wywiadu), `describe.py` (opis osoby, wywiadu i osi dla modelu; `interview_questions`: następne pytanie wywiadu, słowo w słowo, z narzędziem do zapisu odpowiedzi).
  - `app/services/params.py` — wczytanie `params/2026.json`. `app/services/sessions.py` — magazyn sesji (Supabase albo pamięć). `app/assistant/transcript.py` — historia modelu jako wiadomości dla UI (bez ukrytych promptów zdarzeń). `params/2026.json` — liczby i reguły ze źródłami.
  - `tests/` — silnik (`test_engine.py`), zgodność cytatów z Przewodnikiem i Kodeksem pracy (`test_sources.py`), onboarding i wywiad przez API na skryptowanym modelu (`test_chat_api.py`).
- `frontend/` — React 19, TypeScript, Vite 8, Tailwind 4, Oxlint, Motion, lucide-react, react-markdown. Alias `@/` = `src/`.
  - `src/index.css` — tokeny motywu ZUS (`@theme`: kolory, cienie, animacje wejścia), font Lato.
  - `src/types.ts` — kopia modeli backendu i protokołu czatu (trzymaj w zgodzie z `engine/models.py` i `api/chat.py`); `src/api.ts` — `streamChat` (NDJSON).
  - `src/hooks/useAssistant.ts` — stan rozmowy, przywracanie po odświeżeniu, `stop`, `reset`, `calculate` i `load` (start od daty z onboardingu). `src/lib/session.ts` — identyfikator sesji w `localStorage`.
  - `src/components/onboarding/` — pełnoekranowy start przed osią (`Onboarding.tsx`: kroki i nawigacja, `Calendar.tsx`: własny kalendarz bez natywnego `input type=date`, `ChoiceCard.tsx`: karty wyboru i przycisk, `motion.ts`: warianty ruchu). Ikony w `src/assets/onboarding/*.webp`.
  - `src/components/ui/` — komponenty ze Spectrum UI: `text-states` (bez zmian) oraz `agent-steps`, `prompt-composer`, `chat-empty-state`, `nav-list-card` (dostosowane; nagłówek pliku mówi, co zmieniono). `src/lib/ease.ts` — tokeny ruchu Spectrum UI, `src/lib/utils.ts` — `cn`.
  - `src/components/layout/` — lewy pasek ikon (desktop), dolna nawigacja (telefon), widok założeń.
  - `src/components/timeline/` — `CaseNotes` (karta „Twoja sytuacja”: po dwie linie na punkt, całość i źródła po rozwinięciu), `Pulse` (pierścień wokół tego, co się zmieniło), `PillTimeline` (oś z pigułek, szeroki ekran; odległy termin jest przypięty do prawej krawędzi i nie rozciąga skali), `VerticalTimeline` (lista, telefon i wąska kolumna), `ElementDetails` (szczegóły ze źródłem).
  - `src/components/documents/` — lista potrzebnych dokumentów; `src/components/chat/` — rozmowa.
- `supabase/` — `config.toml`, `migrations/` (SQL), `seed.sql`.
- `tools/zus-data/` — pipeline danych ZUS (OCR, katalog spraw). `tools/przewodnik/` — tekst Przewodnika dla asystenta.
- `tools/illustrations/` — generator ikon onboardingu (OpenRouter, Nano Banana 2.1): `style.txt` + `subjects/<nazwa>.txt`, oryginały w `png/`, wzorem stylu jest `png/mama.png`; do aplikacji trafia WebP 640 px z przezroczystym tłem, przycięty do rysunku.
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

## Design i UI

Naszym zadaniem jest pokazać rodzicowi informacje, których potrzebuje. Nic więcej.

- **Bez zagracenia (clutter).** Każdy element ekranu musi odpowiadać na pytanie rodzica. Jeśli nie odpowiada, usuń go.
  - Jeden ekran = jedna główna rzecz (oś czasu). Szczegóły pokazujemy dopiero po kliknięciu elementu.
  - Nie dodawaj atrap nawigacji, pustych kafelków ani ozdobników bez funkcji.
  - Krótkie etykiety, dużo światła między elementami. Tekst prawny i cytaty tylko w szczegółach elementu.
  - Zanim dodasz nowy element na ekran, sprawdź, czy nie da się tej informacji pokazać w istniejącym.
- **Wzór wyglądu**: dashboard ze zrzutu, który dostaliśmy od zespołu (kalendarz zadań z kolorowymi „pigułkami”). Bierzemy z niego:
  - wąski lewy pasek z logo i ikonami widoków,
  - środek: tytuł, pasek dat, pod nim oś z zaokrąglonych pigułek ułożonych kaskadowo (kółko z inicjałem, tytuł, podtytuł, kółko z liczbą na końcu), legenda na dole,
  - prawa kolumna: trzy kolorowe kafelki z liczbą, krótka lista z ikoną i strzałką, niżej karta (u nas: rozmowa z asystentem),
  - białe karty na jasnym tle, duże zaokrąglenia, miękkie cienie, dużo pustej przestrzeni.
- **Kolory: zieleń i biel ZUS** (sprawdzone na zus.pl 21.11.2026). Tokeny są w `frontend/src/index.css` (`@theme`), w komponentach używaj nazw tokenów, nie kodów hex.
  - zieleń główna `#007834`, ciemna `#025a28` — akcje, mama, zaznaczenia,
  - granat `#283754` — tata, tekst nagłówków,
  - bursztyn `#fab856` — ważne dni i terminy,
  - czerwień `#cd0000` — tylko minięte terminy i błędy,
  - tło białe i bardzo jasna szarozieleń; font Lato (jak na zus.pl).
  - Nie używamy logo ZUS ani nie udajemy strony ZUS: to tylko paleta.
- **Komponenty i animacje: Spectrum UI** (ui.spectrumhq.in, komponenty „kopiuj-wklej” na shadcn/ui + Tailwind + Motion). Kopiujemy je do `frontend/src/components/ui/` i przestawiamy na nasze tokeny kolorów. Nowy komponent UI najpierw szukaj w Spectrum UI, dopiero potem pisz własny.
  - Animacje komponentów bierzemy ze Spectrum UI (Motion). Animacja ma pokazywać zmianę (nowy element, przeliczona oś, otwarte szczegóły), a nie zdobić.
  - Szanuj `prefers-reduced-motion`.
- **Układ ekranu** (stan na 21.11.2026):
  - Desktop: pasek ikon | oś czasu (pasek miesięcy, pigułki, legenda, pod spodem szczegóły klikniętego elementu) | prawa kolumna (dokumenty, rozmowa).
  - Telefon: dolna nawigacja Rozmowa / Oś czasu / Założenia; oś jako lista.
  - Onboarding (nowa rozmowa, przed osią): jedno pytanie na pełnym ekranie, bez paska postępu, przejścia blur + przesunięcie. Kroki: kim jesteś (mama/tata) → czy dziecko już jest → ile dzieci → data (kalendarz: przewidywana albo data urodzenia) → jak pracujesz → zarobki (pomijane, gdy nie pracuje) → liczenie → oś. Odpowiedzi zapisują się w sesji (`PUT /api/session/{id}/onboarding`). Zaraz potem asystent sam omawia oś (zdarzenie `timeline_ready`) i kończy następnym pytaniem wywiadu. Na telefonie po onboardingu otwiera się zakładka osi, a „Rozmowa” dostaje kropkę. Każda wizyta zaczyna się od ekranu startowego wywiadu. Gdy przeglądarka ma zapisaną sesję (odpowiedzi z wywiadu albo rozmowę), ekran proponuje „Zacznij nowy wywiad” i „Wróć do zapisanej osi czasu” z krótkim podsumowaniem. Nowy wywiad nadpisuje zapisaną sesję dopiero po ukończeniu; wycofanie się niczego nie kasuje.
  - Kolor pigułki mówi, czym jest odcinek: zielony = urlop mamy, jasnozielony = do wyboru (jeszcze nie zdecydowano: okno przed porodem, urlop uzupełniający, urlop rodzicielski), szaroniebieski = praca. Dokument jest kółkiem z ikoną przed pigułką, której dotyczy.
  - Karta „Twoja sytuacja” jest zwinięta (tytuł i dwie linie każdego punktu), żeby oś była widoczna od razu; jeden przycisk rozwija całe wyjaśnienie ze źródłami. W szczegółach elementu widać dwa pierwsze cytaty z Przewodnika, reszta i Kodeks pracy są pod przełącznikami.
  - Przeliczona oś tylko podświetla zmianę: bursztynowy pierścień wokół zmienionych pigułek i wokół zmienionych punktów „Twojej sytuacji” (ten sam `Pulse`). Szczegóły otwiera kliknięcie albo narzędzie `explain_timeline_element`. Na telefonie podświetlenie od asystenta tylko zaznacza element, nie przewija osi (zakładka przewinie się do niego po otwarciu).

## Fazy — jeden punkt Przewodnika naraz

Rdzeniem aplikacji jest tłumaczenie procesu na podstawie oficjalnego dokumentu ZUS. To, co pokazuje oś i UI, wynika ściśle z tekstu Przewodnika.

Zasady pracy:
- Robimy jedną fazę naraz. Faza to jeden punkt Przewodnika: wchodzi do wywiadu, na oś i do testów.
- W kodzie jest tylko to, co obejmują zrobione fazy. Nie dodawaj elementów „na zapas” z kolejnych punktów ani z innych sekcji. Sekcje „Ściąga domenowa” i „Interakcje” niżej to wiedza na przyszłe fazy, nie lista rzeczy do zaimplementowania teraz.
- Każdy element osi ma dosłowny cytat z sekcji Przewodnika albo z przepisu Kodeksu pracy. Przewodnik jest głównym źródłem; Kodeks pracy uzupełnia to, czego Przewodnik nie podaje (np. wymiar przy wieloraczkach). Gdy punkt Przewodnika opiera się na zdaniach z innej strony (np. kto jest ubezpieczony), cytujemy tylko te zdania, bez reguł z tamtej sekcji. `tests/test_sources.py` sprawdza, że każdy cytat istnieje w tekście źródła co do znaku (literówki oryginału Przewodnika zostają) i że leży na stronie, którą podajemy. W UI przepisy są schowane pod „Podstawa prawna”, żeby nie zagracać karty.
- Poprzednia, szersza wersja (macierzyński, rodzicielski, ojcowski, wnioski, 81,5%, kafelki) jest w gicie w commicie `d2b261d`. Przenosimy z niej rzeczy dopiero w ich fazie.
- Odpowiedzi z onboardingu zapisujemy wszystkie, także te, których żadna faza jeszcze nie liczy (praca, zarobki). Asystent je zna, nie pyta o nie drugi raz i niczego z nich nie wylicza, dopóki nie dojdzie faza, która ich używa. Praca i zarobki dotyczą osoby wypełniającej: gdy wypełnia tata, to jego praca, nie mamy.

Sekcja A „Zasiłek macierzyński dla kobiety” (s. 5–6), podział na fazy:

| Faza | Punkt | Kawałki | Stan |
|---|---|---|---|
| 1 | Przygotowanie do porodu (s. 5) | A1 urlop do 6 tyg. przed przewidywaną datą porodu; A2 zaświadczenie lekarskie o przewidywanej dacie porodu; A3 praca do dnia porodu, zasiłek po urodzeniu | zrobiona |
| 2a | Urodzenie dziecka (s. 5): wymiar i 14 tygodni | A5 wymiar wg liczby dzieci (20/31/33/35/37 tyg., KP art. 180 § 1); A6 14 tyg. po porodzie osobiście; tygodnie przed porodem wliczają się do wymiaru (KP art. 180 § 3); tydzień = 7 dni (KP art. 183¹ § 1); bez urlopu przed porodem start w dniu porodu (KP art. 183¹ § 2) | zrobiona |
| 2b | Urodzenie dziecka (s. 5–6): rodzicielski | A8 rodzicielski po macierzyńskim: 41/43 tyg. łącznie dla obojga rodziców, 9 tyg. wyłącznie dla każdego z nich, więc mama najwyżej 32/34 (s. 7; KP art. 182¹ᵃ); A9 jednorazowo albo do 5 części; A10 do końca roku 6. urodzin (KP art. 182¹ᶜ) | zrobiona |
| 2c | Urodzenie dziecka (s. 5–6): uprawnienia | A4 prawo po porodzie dla ubezpieczonej: etat = ubezpieczenie obowiązkowe, zlecenie i JDG = dobrowolne, liczy się dzień porodu (s. 3, 4–5, 10); A11 „Za życiem”: rodzicielski 65/67 tyg. (KP art. 182¹ᵃ § 2) | zrobiona |
| 2d | Urodzenie dziecka (s. 5): uzupełniający | A7 uzupełniający urlop macierzyński: tydzień za tydzień pobytu dziecka w szpitalu, do 15 albo 8 tyg. (sekcja C s. 8; KP art. 180²) | zrobiona |
| 3 | Martwe urodzenie albo zgon dziecka (s. 6) | A12 przed 8 tyg. życia; A13 po 8 tyg.; A14 wieloraczki | do zrobienia |
| 4 | Dokumenty i wnioski (s. 6) | A15 pracownica: wniosek do pracodawcy; A16 ZAM do ZUS, zlecenie z Z-3a; A17 załączniki | do zrobienia |

Fazy 1 i 2 w szczegółach:
- Wywiad (pyta tylko o to, czego nie dał onboarding; kolejność i słowa pytań wyznacza `interview_questions`): (1) data: przewidywana data porodu albo data urodzenia, (2) ile dzieci przy jednym porodzie, (3) ubezpieczenie: jak pracuje mama (gdy wypełnia tata albo nie wiadomo kto), a przy zleceniu i JDG czy jest zgłoszona do dobrowolnego ubezpieczenia chorobowego; bez ubezpieczenia wywiad się kończy, (4) urlop przed porodem: dziecko w drodze — ile tygodni albo praca do dnia porodu; dziecko urodzone — czy mama była na urlopie przed porodem, (5) tylko dla dziecka w drodze z urlopem przed porodem: zaświadczenie lekarskie, (6) tylko dla dziecka urodzonego: wcześniak albo pobyt w szpitalu, a potem tydzień ciąży, masa do 1000 g i daty pobytów. O zaświadczenie „Za życiem” asystent nie pyta: zapisuje je, gdy rodzic sam o nim powie (informacja jest w szczegółach urlopu rodzicielskiego).
- Oś, dziecko w drodze: znacznik terminu porodu; przed decyzją jasna pigułka „do wyboru” na okno 6 tygodni; po decyzji zielona pigułka urlopu z dokumentem albo pigułka „praca do dnia porodu”; przy urlopie krótszym niż 6 tygodni znacznik najwcześniejszego startu.
- Oś, dziecko urodzone: znacznik narodzin; urlop wzięty przed porodem jako zielona pigułka; bez dokumentu (już niepotrzebny). Gdy urlop się skończył — ostrzeżenie.
- Oś, gdy znana jest liczba dzieci (faza 2a): pigułka „Urlop macierzyński po porodzie” do końca wymiaru (wymiar liczony od startu urlopu, więc tygodnie sprzed porodu skracają część po porodzie) i znacznik końca 14 tygodni po porodzie.
- Ubezpieczenie (faza 2c): mama na etacie jest ubezpieczona obowiązkowo; na zleceniu i z JDG tylko gdy jest zgłoszona do dobrowolnego ubezpieczenia chorobowego; niepracująca nie jest. Dopóki tego nie wiadomo, oś rysuje się przy założeniu, że jest ubezpieczona. Bez ubezpieczenia na osi zostaje tylko dzień porodu i punkt „Uwaga” z wyjaśnieniem. Mama, która nie jest pracownicą, nie dostaje urlopu, tylko zasiłek za ten sam okres (s. 4): mówi o tym punkt „Uprawnienie” i szczegół pigułki.
- Oś po urlopie macierzyńskim (fazy 2b i 2d): jasna pigułka „Uzupełniający urlop macierzyński” (tylko dziecko urodzone, gdy pobyt w szpitalu daje co najmniej tydzień; mama albo tata), potem jasna pigułka „Urlop rodzicielski — do wyboru” z całą częścią mamy (łączny wymiar minus 9 tyg. taty) i znacznik ostatniego dnia: 31.12 roku, w którym dziecko kończy 6 lat. Gdy ten dzień minął: ostrzeżenie zamiast pigułki.
- Urlop uzupełniający liczymy z dat pobytów w szpitalu (KP art. 180² § 1–3): okno 15 tygodni (przed ukończeniem 28. tygodnia ciąży albo masa do 1000 g), 8 tygodni (po 28. i przed ukończeniem 37. tygodnia, masa ponad 1000 g) albo od 5. dnia do końca 8. tygodnia (po 37. tygodniu, pod warunkiem 2 kolejnych dni, z których pierwszy przypada między 5. a 28. dniem). Dni w oknie sumujemy, niepełny tydzień w górę. Pobyt bez daty końca liczymy do dziś i mówimy, że wymiar może wzrosnąć. Założenie: dni „po porodzie” liczymy od dnia następującego po dniu porodu (patrz „Otwarte pytania”).
- Poza zakresem: urlop taty i urlop ojcowski, podział rodzicielskiego między rodziców i na części, łączenie z pracą, kwoty i stawki, wnioski i ich terminy (także 21 dni na wniosek o urlop uzupełniający i rodzicielski), zasiłek po ustaniu ubezpieczenia.

## Wyjaśnianie przypadku — zasada dla każdej fazy

Sama oś to za mało: rodzic ma zrozumieć, co go dotyczy, dlaczego i co z tego policzyliśmy. Zasada obowiązuje w każdej fazie, także w kolejnych punktach sekcji A i w następnych sekcjach Przewodnika.

Dla każdego przypadku pokazujemy, w tej kolejności:
1. **Sytuację** — w jakim przypadku jest rodzina i co to zmienia. Np. „Dziecko urodziło się dzisiaj — to upraszcza sprawę: nie trzeba już planować urlopu przed porodem ani zdobywać zaświadczenia…”, „Dziecko jest w drodze — liczymy od przewidywanej daty porodu”.
2. **Możliwości i ułatwienia** — z czego rodzina może skorzystać i dlaczego. Np. urlop można zacząć nawet 6 tygodni przed przewidywaną datą porodu; przy bliźniętach urlop jest dłuższy (31 tyg. zamiast 20).
3. **Co policzyliśmy** — konkretne daty i długości oraz reguła, z której wynikają (np. tygodnie sprzed porodu wliczają się do wymiaru, więc po porodzie zostaje mniej).
4. **Co przygotować**, jeśli coś trzeba (np. zaświadczenie lekarskie do konkretnego dnia).

Jak to robimy:
- Wyjaśnienie układa silnik, deterministycznie: `backend/app/engine/explain.py` → `Timeline.notes` (`CaseNote` z rodzajem `situation`, `right` — uprawnienie, `risk` — co stoi na przeszkodzie, `choice`, `relief` albo `computed`). Daty czyta z gotowej osi, nie liczy ich drugi raz.
- Każde twierdzenie o zasadach ma cytat. Bez źródła może być tylko opis naszego liczenia (punkt `situation`). Pilnuje tego `tests/test_sources.py`.
- UI pokazuje wyjaśnienie w karcie „Twoja sytuacja” nad osią czasu. Asystent dostaje te same punkty razem z ich źródłami i mówi w tej samej kolejności. Nie dodaje ulg ani możliwości spoza źródeł i każde zdanie podpiera tylko źródłem, które je zawiera.
- Asystent reaguje na oś sam, razem z jej zmianą: po onboardingu (zdarzenie `timeline_ready`) omawia całe wyjaśnienie, a po każdej odpowiedzi w czacie tylko punkty, które się zmieniły (`changed_note_ids`; wynik narzędzia je wymienia, UI podświetla je w karcie). Kończy następnym pytaniem wywiadu, które wyznacza kod (`interview_questions`), nie model.
- Piszemy dokładnie to, co mówi źródło. Przewodnik mówi, że urlop można **zacząć** 6 tygodni przed przewidywaną datą porodu; nie mówi, kiedy złożyć wniosek (to dojdzie z punktem „Dokumenty i wnioski”).
- Każda nowa faza dopisuje swoje punkty w `explain.py` i testy w `tests/test_engine.py`.

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
  - Tabela `sessions` (`id`, `scenario`, `history`): rozmowa i odpowiedzi z wywiadu, jeden wiersz na sesję przeglądarki. RLS bez polityk, więc klucz publiczny nie ma do niej dostępu; czyta i zapisuje ją tylko backend kluczem sekretnym.
  - Migracje na hostowanym projekcie stosujemy przez `npx supabase db push` (po `supabase login` i `supabase link`) albo wklejając plik SQL w SQL Editor. Sam klucz sekretny nie pozwala tworzyć tabel.
  - Bez ustawień Supabase albo przed zastosowaniem migracji sesje są w pamięci procesu; `/api/health` pokazuje w polu `sessions`, gdzie są (`supabase` albo `memory`).
- **Daty**: `datetime.date`, tydzień = `timedelta(days=7)` (7 dni kalendarzowych), przedziały liczone włącznie, „dziś” w strefie Europe/Warsaw (`zoneinfo`).
- **Asystent (czat)**: aplikacja zaczyna się od rozmowy. Agent Pydantic AI (`app/assistant/agent.py`) prowadzi wywiad: jedno pytanie naraz, w kolejności z `interview_questions`. Dosłowny tekst sekcji bieżących faz jest zawsze w instrukcjach modelu, więc model nie musi niczego wyszukiwać. Narzędzia (fazy 1 i 2):
  - zmieniające `Scenario`: `set_due_date`, `set_birth_date`, `set_children_count`, `set_leave_before_birth`, `set_medical_certificate`, `set_mother_work`, `set_voluntary_insurance`, `set_za_zyciem`, `set_hospital_care`,
  - `explain_timeline_element` — podświetla element osi i zwraca zasadę z dosłownym cytatem.

  Na pytania spoza bieżących faz asystent odpowiada, że ten etap aplikacji ich nie obejmuje. Nie odpowiada z wiedzy ogólnej.

  Każde narzędzie zmieniające scenariusz woła `build_timeline` i wysyła zdarzenie `TimelineUpdated` (`ctx.emit`, `CustomEvent`) z osią, listą zmienionych elementów i listą zmienionych punktów wyjaśnienia (`changed_notes`); UI przerysowuje oś w trakcie odpowiedzi. Błąd reguły (`ScenarioError`) zamienia się w `ModelRetry` z polskim komunikatem.

  `POST /api/chat` przyjmuje `session_id` i `message` albo `event` i strumieniuje NDJSON ze zdarzeniami `text`, `tool-call`, `tool-result`, `timeline`, `focus`, `done` i `error`. Historię i `scenario` trzyma serwer w tabeli `sessions`: scenariusz zapisuje po każdym narzędziu, historię na końcu tury. Przeglądarka pamięta tylko identyfikator sesji i po odświeżeniu pobiera rozmowę i oś z `GET /api/session/{id}` (oś jest przeliczana od nowa z zapisanych odpowiedzi). Bez klucza LLM czat zwraca 503, a `/api/timeline` działa dalej.

  Zdarzenia z aplikacji: gdy oś zmienia się poza rozmową, frontend wysyła `event` zamiast wiadomości. Jedyne zdarzenie to `timeline_ready`: wywiad z onboardingu się skończył albo wrócono do zapisanej osi bez rozmowy. Serwer zamienia je w ukryty prompt (`timeline_ready_prompt`, zaczyna się od `⟦Zdarzenie z aplikacji⟧`) z następnym pytaniem wywiadu. Prompt zostaje w historii modelu, ale `transcript.py` go nie pokazuje, więc po odświeżeniu widać tylko odpowiedź asystenta.

  Nowa faza to: sekcja w `guide.py` (albo przepis w `extract_kp.py`), cytaty w `params/2026.json`, pole w `Scenario`, reguła w silniku z testem, punkty wyjaśnienia w `explain.py` z testem, pytanie w wywiadzie (`prompts.py`, `interview_questions` z narzędziem do zapisu) i narzędzie w agencie, etykieta w `toolLabel` (frontend). Jeśli onboarding już zbiera potrzebną odpowiedź, użyj jej zamiast pytać w czacie.
- **LLM**: Claude przez Pydantic AI (`pydantic-ai-slim[anthropic,openrouter]`, wersja 2.x). Dostawca z `LLM_PROVIDER`: `openrouter` (domyślnie, klucz `OPENROUTER_API_KEY`, model `anthropic/claude-opus-5.5`) albo `anthropic` (klucz `ANTHROPIC_API_KEY`, model `claude-opus-5-5`). `LLM_MODEL` nadpisuje model, `LLM_THINKING` wysiłek myślenia. Wybór modelu: `app/api/deps.py`. API wersji 2.x różni się od 1.x, np. `run_stream_events` jest context managerem, a zdarzenia własne idą przez `ctx.emit`. Przed użyciem sprawdzaj źródła w `backend/.venv`. Do czego używamy LLM:
  - czat zbierający fakty i tłumaczący oś (wyżej),
  - asystent Q&A z cytatami — Claude citations na PDF-ach materiałów zwracają dosłowny `cited_text` i numer strony; nie łączyć z `output_config.format`, bo API zwraca 400,
  - odczyt sprawy ze skanu (vision) do postaci `Scenario`, z numerami stron,
  - objaśnienia słowne.

  **Nigdy nie liczy kwot ani dat.** Każda funkcja AI jest oznaczona w UI (wymóg wyzwania).
- **Atrapy** (bez prawdziwych integracji): mObywatel, dane z ZUS, zadłużenie składkowe, e-ZLA, PUE/eZUS, wypełnianie i wysyłka wniosków, odpis aktu urodzenia, organizacje wsparcia, linki zus.pl / gov.pl / PIP.

## Dane i poufność — twarde zasady

- `docs/dokumentyZUS/` jest w `.gitignore`. Dokumenty ZUS są „wyłącznie na użytek HackNation”: nie commituj ich, nie wklejaj treści do commitów, issue ani PR i nie kopiuj do `public/`.
- Nazwy plików spraw zawierają imiona. W UI, logach i testach używaj ID `S01–S86` z katalogu.
- Nie wysyłaj skanów spraw do zewnętrznych API, dopóki mentorzy ZUS tego nie potwierdzą. Hostowany Supabase to też zewnętrzna usługa: danych ze spraw nie trzymamy w nim ani w `seed.sql`. Lokalny Supabase w Dockerze jest OK. W tabeli `sessions` są tylko rozmowy użytkowników aplikacji (prosimy w UI, żeby nie podawali danych osobowych).
- Sprawy to skany bez warstwy tekstowej: odręczne daty, obrócone strony, ok. 15% stron pustych. OCR (tesseract) służy tylko do wyszukiwania i kategorii — **nie do liczb**, bo myli cyfry. Liczby czyta model z obrazu strony.
- Pipeline: `tools/zus-data/run.sh` → `docs/dokumentyZUS/{materialy,sprawy,ocr,katalog_spraw.md,katalog_spraw.json}`. Duplikat „Dariusz Go_3 … (1)” jest pomijany.

## Testy

- Jednostkowe dla każdej reguły i interakcji: przykłady z Przewodnika i liczby z Załącznika. Oczekiwane daty liczymy ręcznie i wpisujemy na sztywno, nie kopiujemy logiki silnika.
- Czat testujemy bez klucza i bez sieci: `FunctionModel` (Pydantic AI) odgrywa wywołania narzędzi, a model podmienia `app.dependency_overrides[get_chat_model]`.
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
- Urlop ojcowski „do ukończenia przez dziecko 12 miesięcy”: przyjmujemy, że musi skończyć się najpóźniej dzień przed 1. urodzinami. Czy to poprawne?
- Wniosek o urlop macierzyński: w materiałach nie ma terminu. Na osi pokazujemy go na dzień startu urlopu, bez etykiety „termin”.
- Uzupełniający urlop macierzyński (KP art. 180² § 1): jak liczyć „5. dzień po porodzie” i „do upływu 8./15. tygodnia po porodzie” — czy dzień porodu się wlicza? Przyjmujemy, że nie: n-ty dzień po porodzie to data urodzenia + n dni. Materiały tego nie rozstrzygają.
- Poradnik pisze, że z urlopu uzupełniającego można skorzystać, „jeśli dziecko przebywa w szpitalu co najmniej 5 dni po narodzinach”, a KP art. 180² § 1 pkt 1–2 nie stawia takiego warunku wcześniakom. Liczymy według Kodeksu pracy.
- Czy mama może wykorzystać 9 tygodni urlopu rodzicielskiego przypadające tacie, gdy taty nie ma albo nie jest ubezpieczony? Przyjmujemy, że nie (KP art. 182¹ᵃ § 4): mama ma najwyżej 32/34 tyg. (56/58 z „Za życiem”).
- Mama niepracująca: przyjmujemy, że nie podlega ubezpieczeniu chorobowemu. Wyjątki „po ustaniu ubezpieczenia” (Przewodnik s. 4) dojdą w osobnej fazie.

## Konwencje

- UI i treści po polsku. Kod, identyfikatory i commity po angielsku.
- Python: ruff (linia 100), adnotacje typów wszędzie, modele Pydantic na granicy API. TypeScript: oxlint + `tsc -b`, komponenty funkcyjne, style w Tailwind.
- Sekrety tylko w `backend/.env` i `frontend/.env.local` (oba w `.gitignore`). Nowa zmienna = wpis w odpowiednim `.env.example`.
- Nowa reguła = źródło (dokument + strona albo artykuł) + test. Bez źródła nie wchodzi.
- Język odpowiedzi dla rodzica: prosty, konkretny („dostaniesz”, „złóż do”), z odnośnikiem do źródła. Przy trudnych sytuacjach — empatycznie.
