# Zasiłkowy Przewodnik Przyszłego Rodzica – plan funkcji

Wyzwanie ZUS, HackNation. Dokument roboczy: co budujemy, w jakiej kolejności i po co.

## 1. Idea w jednym zdaniu

Towarzysz rodzica od ciąży do powrotu do pracy: jedna oś zakotwiczona w dniu porodu, która po każdej zmianie sytuacji przelicza, co się należy, od kiedy, ile i co trzeba zrobić.

## 2. Zasady projektu

- **Poród jest środkiem osi.** Wszystko układa się przed nim i po nim.
- **Liczy silnik reguł, nie AI.** Kwoty i werdykty są deterministyczne i mają wyjaśnienie.
- **Najpierw wartość, potem logowanie.** Wstępny wynik w niecałą minutę.
- **Użytkownik mówi, co się stało, a nie zna przepisów.**
- **Reguły to dane, nie kod.** Zmiana prawa to zmiana w panelu administracyjnym.
- **Każdy wynik odpowiada na trzy pytania:** co się należy, ile i do kiedy, co mam zrobić.

## 3. Flow użytkownika

### Onboarding (cel: wynik po trzech pytaniach)

1. **Kiedy rodzi się dziecko?** Termin porodu albo data urodzenia. Adopcja i rodzina zastępcza jako link pod spodem.
2. **Jak pracujesz?** Etat, zlecenie, własna firma, nie pracuję. Od kiedy.
3. **Ile zarabiasz?** Przedział albo „nie wiem”.
4. **Pierwszy wynik:** „Czy w dniu porodu będziesz mieć prawo do zasiłku macierzyńskiego?” (tak / nie / zagrożone) oraz wstępna oś z widełkami kwot.
5. **Doprecyzowanie** (każda droga zwęża widełki): logowanie przez mObywatela i dane z ZUS (symulacja), wgranie dokumentu, wpisanie ręczne.
6. **Na czym Wam zależy?** Aplikacja proponuje 2–3 gotowe plany.
7. **Zaproszenie drugiego rodzica** (link lub QR, opcjonalnie).
8. **Ekran główny z osią.**

### Trzy odcinki osi

| Odcinek | Co pokazuje |
|---|---|
| Przed porodem | Zwolnienie w ciąży (kod B, 100%), urlop do 6 tygodni przed porodem, czego nie zmieniać w zatrudnieniu, ochrona przed zwolnieniem |
| Poród i pierwsze tygodnie | Akt urodzenia, wniosek do pracodawcy albo ZUS, 21 dni na decyzję o 81,5%, urlop ojcowski |
| Po porodzie | Macierzyński, uzupełniający, rodzicielski, podział z tatą, praca na część etatu, powrót do pracy |

## 4. Funkcje

Priorytety: **P0** musi działać naprawdę, **P1** mocno podnosi ocenę, **P2** jeśli zostanie czas (może być makietą).

### 4.1 Rdzeń

| # | Funkcja | Opis | Priorytet |
|---|---|---|---|
| F1 | Silnik reguł | Ustala prawo, wymiar i wysokość zasiłków na podstawie stanu sprawy. Reguły w konfiguracji z datą obowiązywania. | P0 |
| F2 | Zintegrowany kalkulator | Jeden kalkulator z opcjami: oboje rodzice, liczba dzieci, „Za życiem”, wcześniak, adopcja i rodzina zastępcza, indywidualna podstawa wymiaru. | P0 |
| F3 | Oś rodzicielstwa | Dwa tory (mama, tata), bloki urlopów, znaczniki „dziś” i „poród”, walidacja reguł na żywo (14 tygodni matki, 9 tygodni nieprzenoszalnych, maks. 5 części, termin do końca roku 6. urodzin). | P0 |
| F4 | Kalendarz wypłat | Schodkowy wykres: ile wpływa w którym miesiącu i kto płaci (pracodawca czy ZUS), z zaznaczonymi dołkami. | P0 |
| F5 | „Dlaczego tyle?” | Przy każdej kwocie: podstawa wymiaru, kroki obliczeń, przepis. | P0 |
| F6 | Łączenie urlopu rodzicielskiego z pracą | Suwak 0–50% etatu: jak wydłuża się urlop i jak zmienia się kwota. | P0 |
| F7 | „Coś się zmieniło” | Biblioteka zdarzeń, każde przelicza oś: wcześniak lub szpital, ciąża mnoga, utrata pracy, choroba lub śmierć matki, martwe urodzenie lub zgon dziecka, diagnoza „Za życiem”, zmiana pracy przed porodem. | P0 (3–4 zdarzenia dopracowane, reszta jako szablony) |

### 4.2 Funkcje wyróżniające

| # | Funkcja | Opis | Priorytet |
|---|---|---|---|
| F8 | Planowanie od celu | Użytkownik wybiera cel (najwięcej pieniędzy, najdłużej w domu, równy podział, szybki powrót), silnik układa plany. | P1 |
| F9 | „Zostawiacie na stole” | Licznik niewykorzystanych uprawnień w złotówkach i tygodniach. | P1 |
| F10 | Punkty bez powrotu | Decyzje nieodwracalne jako kłódki na osi z odliczaniem dni. | P1 |
| F11 | Stress-test planu | Jeden przycisk przepuszcza plan przez zdarzenia losowe i pokazuje, gdzie grozi utrata prawa. | P1 |
| F12 | Porównanie wariantów | Plany obok siebie (np. 100% + 70% kontra 81,5%), różnica w kwocie i w czasie. | P1 |
| F13 | Kafelki tygodni | Pula urlopu rodzicielskiego jako siatka do podziału; 9 tygodni przypiętych do każdego rodzica. | P1 |
| F14 | „Nie przysługuje” z dalszą drogą | Dlaczego nie, co zamiast (np. świadczenie rodzicielskie), co zrobić, żeby przysługiwało. | P1 |
| F15 | Jedna rzecz na dziś | Ekran główny zaczyna się od jednego zadania z terminem. | P1 |
| F16 | Animacja zmiany planu | Po zdarzeniu bloki przesuwają się, stary plan zostaje jako cień, obok różnica. | P1 |
| F17 | Wspólny plan pary | Drugi rodzic dopisuje swoje dane przez link, bez konta. Stan zapisany w linku. | P2 |
| F18 | Tryb dyskretny | Planowanie anonimowe na wczesnym etapie ciąży. | P2 |

### 4.3 Dokumenty i wnioski

| # | Funkcja | Opis | Priorytet |
|---|---|---|---|
| F19 | Galeria przykładowych spraw | „Załaduj sprawę” z gotowych danych; działa zawsze, także bez sieci. | P0 |
| F20 | Wgranie dokumentu | Klasyfikacja stron, odczyt pól z kluczowych stron (ZAM, Z-3, Z-3a), ekran potwierdzenia przed liczeniem. | P0 |
| F21 | Gdzie złożyć wniosek | Pracownik, zlecenie czy firma oraz wielkość płatnika: pracodawca albo ZUS. Spersonalizowana lista: co, komu, do kiedy. | P0 |
| F22 | Generator wniosków o urlop | Gotowy wniosek do pracodawcy i wiadomość do kadr; symulacja wysyłki do pracodawcy lub ZUS. | P1 |
| F23 | Sprawdzanie wniosku przed złożeniem | Brakujące pola, niezgodne daty, brak załącznika, nieaktualny formularz (ZUR, ZAO, Z-3b zlikwidowane od 24.10.2026). | P1 |
| F24 | „Przetłumacz pismo z ZUS” | Zdjęcie pisma: co to znaczy, czy coś trzeba zrobić i do kiedy. | P1 |
| F25 | Strażnik terminów | Odliczanie i eksport do kalendarza (.ics). | P2 |

### 4.4 Ryzyka i wsparcie

| # | Funkcja | Opis | Priorytet |
|---|---|---|---|
| F26 | Radar ryzyk | Co grozi utratą lub obniżeniem zasiłku: brak ubezpieczenia w dniu porodu, umowa pozorna, podwyższenie podstawy w ciąży, zadłużenie składkowe. | P0 |
| F27 | Tryb wrażliwy | Dla trudnych zdarzeń: spokojny ton, krótsza ścieżka, uprawnienia (8 tygodni, 7 dni po zgonie), bez głosu i bez radosnych ilustracji. | P1 |
| F28 | Organizacje wsparcia | Podmioty charytatywne dla rodziców po stracie, wcześniaków, dzieci ciężko chorych. | P1 (prosta lista) |
| F29 | Odnośniki | ZUS, Ministerstwo Rodziny, Państwowa Inspekcja Pracy. | P0 (tanie) |

### 4.5 Symulacje wymagane w briefie

| # | Funkcja | Priorytet |
|---|---|---|
| F30 | Logowanie przez mObywatela (wybór persony) | P0 |
| F31 | Pobranie danych o ubezpieczeniu z ZUS (mock na podstawie poświadczeń ze spraw) | P0 |
| F32 | Stan zadłużenia składkowego na dzień powstania prawa | P1 |
| F33 | Podgląd zwolnień e-ZLA | P1 |
| F34 | Połączenie z PUE/eZUS: dane konta i zapytanie | P2 |
| F35 | Wniosek o odpis aktu urodzenia | P2 |

Wszystkie symulacje wyraźnie oznaczone w interfejsie jako dane przykładowe.

### 4.6 Administracja i wdrożenie

| # | Funkcja | Opis | Priorytet |
|---|---|---|---|
| F36 | Panel administracyjny | Edycja parametrów: stawki procentowe, wymiary urlopów, terminy, treści zdarzeń. Wersje z datą obowiązywania. | P0 |
| F37 | Raport zgodności | Wyniki silnika zestawione z rozstrzygnięciami z przykładowych spraw. | P0 |
| F38 | Informacja zwrotna dla ZUS | Zanonimizowane dane: co zaskakuje, gdzie użytkownicy rezygnują. | P2 |
| F39 | Dostępność i języki | Prosty język, WCAG, wersje UA i EN. | P1 (WCAG), P2 (języki) |
| F40 | Głos | Lektor w filmie; przycisk „Posłuchaj” przy wyniku; opcjonalnie wejście głosem. | P2 (lektor w filmie: P0) |

## 5. Pokrycie wymagań z briefu

| Wymaganie | Funkcje |
|---|---|
| a) świadczenia w ciąży, także brak uprawnień | F1, F3, F14, F26 |
| b) kalkulator dla obojga rodziców | F2, F3, F4 |
| c) łączenie pracy z urlopem rodzicielskim | F6 |
| d) symulacja dla obojga rodziców | F3, F12, F13 |
| e), j) adopcja i rodzina zastępcza | F2 |
| f) indywidualna podstawa wymiaru, sprawy z zestawów | F2, F19, F20, F37 |
| g) dokumenty, terminy, gdzie złożyć | F21, F22, F25 |
| h) zagrożenia i ryzyka | F11, F26 |
| i) podmioty charytatywne | F28 |
| mObywatel, dane ZUS, zadłużenie, e-ZLA, PUE, wnioski, akt urodzenia | F30–F35, F22 |
| przekierowania | F29 |
| zmiana parametrów w panelu | F36 |
| upload lub wybór wniosków | F19, F20 |

## 6. Gdzie jest AI

| Funkcja | Rola AI |
|---|---|
| F20 Wgranie dokumentu | Odczyt skanów (model z obsługą obrazu), zawsze z potwierdzeniem użytkownika |
| F23 Sprawdzanie wniosku | Wykrywanie braków i niespójności |
| F24 Tłumaczenie pism | Wyjaśnienie prostym językiem |
| F5 „Dlaczego tyle?” | Opcjonalnie: sformułowanie wyjaśnienia na podstawie kroków z silnika |
| F40 Głos | Synteza mowy |
| Ilustracje | Wygenerowane grafiki faz i zdarzeń |

AI nigdy nie liczy kwot ani nie ustala prawa do zasiłku. Na demo model w chmurze, w opisie wdrożenia ścieżka lokalna (np. Bielik), z jedną warstwą abstrakcji nad dostawcą.

### Agent: wywiad i propozycje (F41, P1)

Czat nie jest głównym flow. Prowadzi wywiad, wypełnia stan sprawy i proponuje plany, a wynik zawsze widać na osi obok rozmowy. Formularz kaflowy działa także bez agenta.

**Zasada:** agent korzysta wyłącznie z przygotowanych narzędzi i z materiałów ZUS. Każdą kwotę, datę i werdykt zwraca narzędzie, nie model.

| Narzędzie | Co robi |
|---|---|
| `ustaw_dane_sprawy` | Zapisuje odpowiedź z wywiadu w stanie sprawy (forma pracy, daty, zarobki, liczba dzieci) |
| `sprawdz_prawo_do_zasilku` | Zwraca: przysługuje / nie przysługuje / zagrożone, z powodem |
| `policz_zasilek` | Wymiar i wysokość dla bieżącego planu, z krokami obliczeń |
| `zaproponuj_plany` | 2–3 plany dla wybranego celu |
| `porownaj_plany` | Różnica w kwocie i w czasie między planami |
| `dodaj_zdarzenie` | Zdarzenie „Coś się zmieniło” i przeliczenie osi |
| `test_odpornosci` | Stress-test planu |
| `lista_krokow` | Co złożyć, komu (pracodawca czy ZUS) i do kiedy |
| `szukaj_w_materialach_zus` | Fragmenty poradnika, wyciągu przepisów i opisu wyzwania, z odnośnikiem do źródła |
| `pobierz_dane_zus` | Symulowane dane o ubezpieczeniu, zadłużeniu i e-ZLA |
| `odczytaj_dokument` | Pola z wgranego wniosku lub pisma |
| `organizacje_wsparcia` | Podmioty pomocowe dla danej sytuacji |

**Zabezpieczenia:**
- Zmiana planu wymaga kliknięcia „Zastosuj”; po niej pojawia się Undo Pill.
- Odpowiedź o przepisach zawsze z cytowanym fragmentem materiałów ZUS; gdy nic nie znaleziono, agent mówi to wprost i odsyła do ZUS.
- Agent pokazuje opcje i ich skutki, decyzję zostawia rodzicom.
- W trybie wrażliwym krótko, spokojnie, bez propozycji optymalizacji.
- Te same narzędzia wywołuje interfejs, więc wynik czatu i formularza jest identyczny.

## 7. Dane testowe

- Teczki spraw to skany bez warstwy tekstowej (ok. 50 stron każda).
- Dla każdej sprawy ręcznie przygotowany plik JSON z kilkunastoma polami i oczekiwanym wynikiem.
- Poświadczenia ubezpieczenia zasilają mock danych ZUS.
- Notatki z rozstrzygnięciem są wzorcem dla raportu zgodności.
- Dokumentów ZUS nie wolno kopiować ani rozpowszechniać: poza publicznym repozytorium, w repozytorium tylko syntetyczne odpowiedniki.

## 8. Reguły do zweryfikowania na materiałach ZUS

- Tabela wymiarów urlopów z załącznika (źródło prawdy dla F1).
- Podwyższenie zasiłku do kwoty świadczenia rodzicielskiego przy niskiej podstawie (widoczne w sprawie „Anna nr 3”, nieopisane w briefie).
- Sposób liczenia podstawy wymiaru dla każdej formy zatrudnienia.
- Zasady wariantu 81,5% przy podziale urlopu między rodziców.
- Kwoty netto: pokazywać jako szacunek albo zostać przy brutto.

## 9. Wygląd i technologia

- **Styl:** biel i ciemna zieleń jako kolor marki; osobne barwy dla rodzajów urlopu, bursztyn dla terminów, czerwień tylko dla utraty prawa.
- **Grafika:** ilustracje z AI na kartach faz i zdarzeń; małe ikony z gotowego zestawu (Lucide lub Phosphor).
- **Frontend:** React / Next.js, Park UI (alternatywnie React Aria Components lub shadcn/ui), oś własna na CSS grid, dnd-kit, Motion.
- **Komponenty dodatkowe:** Spectrum UI (https://ui.spectrumhq.in), kopiowane komponenty React na Tailwind CSS i Motion, instalowane przez CLI shadcn. Na start Undo Pill (https://ui.spectrumhq.in/docs/undo-pill).
- **Backend:** REST API, silnik reguł jako osobny moduł z testami.
- **Prywatność:** dokumenty przetwarzane bez zapisu, klucze tylko po stronie serwera.

### Undo Pill: gdzie go używamy

Pigułka „Cofnij” z pierścieniem odliczania (domyślnie 5 sekund, zatrzymuje się po najechaniu lub fokusie, Escape cofa, ogłaszana czytnikom ekranu jako `role="status"`).

- **Po każdej zmianie na osi** (przesunięcie bloku, dodanie tygodni taty, zmiana etatu): „Plan zmieniony · Cofnij”. Zachęca do eksperymentowania bez obawy, że coś się zepsuje.
- **Po dodaniu zdarzenia „Coś się zmieniło”** (F7): cofnięcie przywraca poprzedni plan, co łączy się z animacją zmiany (F16).
- **Po zastosowaniu gotowego planu** z planowania od celu (F8) i po wyniku stress-testu (F11).
- **Po odhaczeniu „jednej rzeczy na dziś”** (F15) i po usunięciu wgranego dokumentu (F20).
- **Nie używamy** przy symulowanej wysyłce wniosku (F22): tam potrzebne jest wyraźne potwierdzenie przed wysłaniem, a nie cofanie po fakcie.

Wymaga historii stanów sprawy po stronie aplikacji (poprzedni stan do przywrócenia).

## 10. Kolejność prac

1. Model stanu sprawy (JSON) i silnik reguł z testami na 3–4 sprawach.
2. Onboarding i oś z kalendarzem wypłat.
3. Zdarzenia „Coś się zmieniło” (ciąża z kodem B do porodu, wcześniak, tata przejmuje urlop, martwe urodzenie).
4. Galeria spraw, wgranie dokumentu, gdzie złożyć wniosek.
5. Panel administracyjny i raport zgodności.
6. Funkcje wyróżniające: „zostawiacie na stole”, punkty bez powrotu, stress-test, porównanie.
7. Symulacje, tryb wrażliwy, dopracowanie na telefonie.
8. Film (3 minuty, jedna persona), prezentacja (10 slajdów), opis z listą funkcji AI.