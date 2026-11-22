# Zasiłkowy Przewodnik Przyszłego Rodzica — opis funkcji

HackNation 2026, wyzwanie ZUS. Stan aplikacji na 22.11.2026.

## 1. W jednym zdaniu

Aplikacja z sytuacji rodziny buduje osobistą oś czasu od ciąży do powrotu do pracy. Oś mówi, co się należy, od kiedy, ile, kto płaci i jaki wniosek złożyć do kiedy. Gdy coś się zmienia, oś przelicza się i pokazuje różnicę.

## 2. Problem, który rozwiązujemy

- Zasady są rozproszone: Kodeks pracy, ustawa zasiłkowa, dwa rozporządzenia, materiały ZUS.
- Wynik zależy od wielu rzeczy naraz: formy pracy (etat, zlecenie, własna firma), ubezpieczenia chorobowego, liczby dzieci, zarobków, zdarzeń (wcześniak, szpital, utrata pracy, strata dziecka).
- Część decyzji jest nieodwracalna, np. wniosek o stawkę 81,5% można złożyć najpóźniej 21 dni po porodzie.
- Rodzic nie zna przepisów. Wie tylko, co się u niego dzieje.
- ZUS chce jednego zintegrowanego kalkulatora zamiast dziesięciu osobnych (wymagania a–j z opisu wyzwania). U nas tym kalkulatorem jest oś czasu.

## 3. Zasady, na których stoi aplikacja

- **Liczy silnik reguł, nie AI.** Daty, kwoty i odpowiedź „przysługuje / nie przysługuje” są deterministyczne: te same odpowiedzi zawsze dają tę samą oś.
- **Każda zasada ma dosłowny cytat ze źródła** z numerem strony albo artykułu: opis wyzwania ZUS (Przewodnik), Kodeks pracy, ustawa zasiłkowa, Załącznik ZUS, rozporządzenia z 11.03.2025 i 27.09.2026. Test automatyczny sprawdza każdy cytat co do znaku.
- **Reguły to dane, nie kod.** Liczby (tygodnie, stawki, terminy) są w pliku parametrów i w panelu administracyjnym, z datą obowiązywania.
- **Rodzic mówi, co się stało.** Aplikacja tłumaczy to na uprawnienia.
- **Każdy wynik odpowiada na trzy pytania:** co się należy, ile i do kiedy, co mam zrobić.
- **Bez danych osobowych na serwerze.** Imię, PESEL i adres do wniosków zostają w przeglądarce.

## 4. Droga rodzica przez aplikację

1. **Wywiad startowy (onboarding).** Jedno pytanie na pełnym ekranie, karty do kliknięcia, własny kalendarz. Pytania: kim jesteś (mama, tata), czy dziecko już jest (czekamy / już jest / przyjmujemy dziecko), ile dzieci, data porodu albo termin, jak pracujesz, przy zleceniu i firmie zgłoszenie do dobrowolnego ubezpieczenia chorobowego, wielkość płatnika (ponad 20 osób), kwota miesięczna, to samo o drugim rodzicu, zwolnienie lekarskie w ciąży, urlop przed porodem. „Nie wiem” jest zawsze dozwolone.
2. **Skrót:** „Pobierz dane z ZUS przez mObywatel” wypełnia pracę, płatnika, kwotę i zwolnienia (symulacja, wyraźnie oznaczona).
3. **Plan.** Jeden ekran dla telefonu i komputera, ułożony według pytań rodzica: sytuacja jednym zdaniem, „Na dziś”, kafelki-odpowiedzi, oś albo kalendarz, pieniądze, wnioski, narzędzia do dopasowania planu.
4. **Asystent AI obok planu.** Dopytuje o to, czego nie dał wywiad (zwykle 1–3 rzeczy), zapisuje odpowiedzi i tłumaczy oś. Plan działa też bez niego.
5. **Powrót.** Przeglądarka pamięta sesję: można wrócić do zapisanej osi albo zacząć nowy wywiad.

## 5. Oś czasu — serce aplikacji

- **Ścieżki:** Dziecko i zdarzenia, Mama, Tata, Pieniądze, Dokumenty.
- **Okresy** jako klipy, jak w programie do montażu: zwolnienie w ciąży, urlop macierzyński przed porodem i po nim, uzupełniający, rodzicielski w częściach, ojcowski, praca łączona z urlopem.
- **Ważne dni:** termin porodu albo narodziny, koniec 14 tygodni mamy, terminy wniosków, ostatni dzień na 81,5%, ostatni dzień urlopu ojcowskiego, ostatni dzień urlopu rodzicielskiego, koniec ochrony przed zwolnieniem.
- **Kolor mówi, czym jest okres:** zielony to mama, granatowy to tata, jasny przerywany to „do wyboru”, szaroniebieski to praca.
- **Kliknięcie w element** otwiera szczegóły: od kiedy, do kiedy, ile, stawka, kwota, kto płaci, jaki wniosek, podstawa prawna z cytatem.
- **Głowica** przeciągana po linijce, strzałki skaczą między zdarzeniami, zoom jak w programie do montażu.
- **Widok kalendarza:** miesiące z dniami w kolorze tego, kto jest w domu, karta dnia po kliknięciu.
- **Na telefonie:** ta sama oś ze ścieżkami, ułożona pionowo: czas biegnie w dół, kolumny Mama i Tata z okresami w skali, przy każdym okresie długość, daty i kwota miesięczna, ważne dni jako ikony z kłódką przy decyzjach bez powrotu. Szczegóły w arkuszach wysuwanych od dołu.
- **„Dlaczego tak?”:** całe wyjaśnienie przypadku w stałej kolejności: sytuacja, możliwości i ułatwienia, co policzyliśmy, co przygotować. Każdy punkt ze źródłem.
- **„Co przed Wami”:** kroki miesiąc po miesiącu z odliczaniem dni.

## 6. Co liczy silnik reguł

**Prawo do zasiłku**
- Etat: ubezpieczenie chorobowe obowiązkowe. Zlecenie i własna firma: tylko przy zgłoszeniu do ubezpieczenia dobrowolnego. Liczy się dzień porodu.
- Rodzic, który nie jest pracownikiem, nie dostaje urlopu, tylko zasiłek za ten sam okres. Aplikacja mówi to wprost.
- Gdy zasiłek nie przysługuje, aplikacja mówi dlaczego, co jest zamiast i co zrobić, żeby przysługiwał.

**Ciąża**
- Zwolnienie lekarskie w ciąży: pierwsze 33 dni w roku płaci pracodawca (14 dni po 50. roku życia), potem zasiłek chorobowy 100%, najwyżej 270 dni. Prawo po 30 dniach ubezpieczenia obowiązkowego albo 90 dniach dobrowolnego.
- Świadczenie rehabilitacyjne po wyczerpaniu zasiłku.
- Utrata pracy w ciąży (upadłość, likwidacja, śmierć pracodawcy, rozwiązanie umowy z naruszeniem prawa): zasiłek w wysokości zasiłku macierzyńskiego do porodu, potem zasiłek macierzyński po ustaniu ubezpieczenia, wypłacany przez ZUS.
- Zagrożenia: brak ubezpieczenia w dniu porodu, umowa „dla pozoru”, podwyższenie podstawy składek w ciąży, zadłużenie składkowe przy własnej firmie.

**Mama**
- Urlop macierzyński: 20, 31, 33, 35 albo 37 tygodni przy 1, 2, 3, 4 albo 5 i więcej dzieciach. Do 6 tygodni przed przewidywaną datą porodu, 14 tygodni po porodzie mama wykorzystuje sama.
- Uzupełniający urlop macierzyński za pobyt dziecka w szpitalu: tydzień za tydzień, do 8 albo 15 tygodni, liczony z dat pobytów, tygodnia ciąży i masy urodzeniowej.
- Urlop rodzicielski: 41 albo 43 tygodnie na oboje rodziców, 65 albo 67 z zaświadczeniem „Za życiem”. Po 9 tygodni tylko dla każdego z rodziców. Najwyżej 5 części, do końca roku, w którym dziecko kończy 6 lat.

**Tata**
- Urlop ojcowski: 14 dni, w całości albo w dwóch częściach, do dnia przed pierwszymi urodzinami dziecka.
- Jego 9 tygodni urlopu rodzicielskiego i podział reszty puli z mamą.
- Przejęcie urlopu macierzyńskiego po 14 tygodniach mamy.
- Sytuacje szczególne mamy: pobyt w szpitalu, orzeczenie o niezdolności do samodzielnej egzystencji, śmierć, porzucenie dziecka. Także wtedy, gdy mama nie była ubezpieczona.

**Łączenie urlopu rodzicielskiego z pracą**
- Praca do pół etatu wydłuża część urlopu proporcjonalnie. Zasiłek za tygodnie pracy jest odpowiednio niższy.

**Strata dziecka**
- Martwe urodzenie albo śmierć dziecka przed 8. tygodniem życia: 8 tygodni urlopu po porodzie, nie krócej niż 7 dni od dnia śmierci. Później: 7 dni od dnia śmierci. Przy bliźniętach wymiar według żyjących dzieci.

**Przyjęcie dziecka na wychowanie**
- Osobna oś dla adopcji i rodziny zastępczej niezawodowej: urlop na warunkach urlopu macierzyńskiego, granice wieku 7, 10 i 14 lat, najkrótszy urlop 9 tygodni, urlop rodzicielski i ojcowski adopcyjnego taty.

**Kto płaci i ochrona**
- Zasiłek wypłaca płatnik składek, który zgłasza do ubezpieczenia chorobowego ponad 20 osób. W pozostałych przypadkach i przy własnej firmie wypłaca ZUS.
- Pracownicę chroni zakaz zwolnienia. Oś pokazuje, do kiedy trwa ochrona. Umowa na czas określony przedłuża się do dnia porodu.

## 7. Pieniądze

- **Stawki:** 100% podstawy za urlop macierzyński, uzupełniający i ojcowski, 70% za rodzicielski, albo 81,5% za macierzyński i rodzicielski mamy na jej wniosek (9 tygodni drugiego rodzica zawsze 70%).
- **Podstawa wymiaru** z jednej kwoty miesięcznej albo z zarobków miesiąc po miesiącu z zaświadczenia płatnika (Z-3, Z-3a): krótsze ubezpieczenie, miesiące przepracowane w części, premie, najniższa podstawa, górna granica dla osób bez etatu.
- **Przykład policzony przez silnik:** etat, 8 000 zł brutto. Podstawa 6 903,20 zł, dziennie 230,11 zł. Urlop macierzyński 20 tygodni: 32 215,40 zł. Urlop rodzicielski mamy 32 tygodnie po 70%: 36 079,68 zł.
- **„Dlaczego tyle?”:** każda kwota rozpisana krok po kroku, z przepisem przy każdym kroku.
- **Kalendarz wypłat:** słupek za każdy miesiąc, osobno mama i tata, z oznaczeniem, kto wypłaca (pracodawca czy ZUS), miesięcy z niższą stawką i miesięcy bez wypłat.
- **Porównanie stawek:** 100% i 70% obok 81,5%, z różnicą w złotówkach.
- Front niczego nie liczy. Układa tylko liczby silnika. Suma miesięcy zgadza się z sumą wypłat co do grosza.

## 8. Decyzje i przewidywanie — nasze wyróżniki

- **„Na dziś”:** ekran zaczyna się od jednej najważniejszej rzeczy z terminem.
- **Plany dla Was:** rodzic wybiera cel (najwięcej pieniędzy, najdłużej w domu, równy podział, szybki powrót do pracy). Silnik układa 2–3 plany z liczbami: dni urlopu, dzień powrotu do pracy, kwoty, z czego rodzina rezygnuje. Jeden klik układa wybrany plan na osi.
- **Podział urlopu rodzicielskiego:** suwak mama–tata na pasku tygodni. Tygodnie „tylko dla jednego rodzica” są przypięte. Kolejność i praca do pół etatu w tym samym miejscu. Każdy ruch przelicza silnik.
- **„Co, jeśli coś pójdzie inaczej?”:** test odporności planu. Aplikacja przepuszcza plan przez zdarzenia, które jeszcze mogą się zdarzyć (bliźnięta, wcześniak, utrata pracy w ciąży, przejęcie urlopu przez tatę, „Za życiem”) i mówi, czy prawo zostaje, jest zagrożone, czy przepada, z różnicą kwot.
- **Podgląd zdarzenia na prawdziwej osi:** stary plan zostaje jako cień, baner mówi, co doszło, co się przesunęło, co znika i co płaci inaczej. Nic się nie zapisuje, dopóki rodzic nie powie „To się stało”.
- **„Nie zostawiajcie tego na stole”:** niewykorzystane uprawnienia w tygodniach i złotówkach, z ostatnim dniem, do którego można z nich skorzystać.
- **Punkty bez powrotu:** decyzje nieodwracalne jako kłódki na osi z odliczaniem dni: 81,5%, urlop ojcowski, ostatni dzień urlopu rodzicielskiego.
- **„Na co uważać”:** ryzyka dopasowane do formy pracy.
- **Cofnij:** po każdej zmianie planu pigułka „Cofnij” przez 5 sekund. Zachęca do próbowania.

## 9. Wnioski i dokumenty

- **Lista „co, komu, do kiedy”:** każdy wniosek jest na osi przed okresem, którego dotyczy, z adresatem (pracodawca, płatnik albo ZUS).
- **Terminy z Kodeksu pracy:** urlop rodzicielski 21 dni przed, ojcowski 7 dni, uzupełniający 21 dni przed końcem macierzyńskiego, przejęcie urlopu przez tatę 14 dni, rezygnacja mamy 7 dni, praca w czasie urlopu 21 dni. Gdy materiały nie podają terminu, aplikacja mówi to wprost i nie nazywa daty terminem.
- **Wniosek wypełniany na samym dokumencie:** wniosek o urlop jako pismo do pracodawcy, ZAM i ZAS-53 w układzie druku ZUS. Pola i załączniki pochodzą z rozporządzeń. To, co wynika z planu, jest już wpisane.
- **Pobranie w PDF:** gotowe pismo z podstawą prawną, oświadczeniami i listą załączników. Dla ZAM i ZAS-53 zestawienie danych i informacja, gdzie jest oficjalny wzór.
- **„Sprawdź wniosek”:** brakujące pola, daty niezgodne z planem, brak załącznika, formularz zlikwidowany od 24.10.2026 (ZUR, ZAO, Z-3b). Reguły bez AI.
- **Wiadomość do kadr** gotowa do skopiowania.
- **Teczka:** wszystkie wnioski w jednym PDF, plan na kartce A4, lista dokumentów do odhaczania.
- **Do kalendarza:** terminy jako plik .ics z przypomnieniem.
- **Udostępnij:** link do planu tylko do odczytu dla drugiego rodzica, bez logowania i bez danych osobowych.
- **„Pismo z ZUS” (AI):** zdjęcie albo PDF pisma. Aplikacja mówi prostym językiem, co to za pismo, co zrobić i do kiedy. Daty są tylko przepisane z pisma, każdy punkt ma cytat i stronę.

## 10. Trudne sytuacje

- Aplikacja nigdy nie pyta o stratę dziecka. Zapisuje ją, gdy rodzic sam o niej powie.
- **Tryb łagodny:** bez kafelków i propozycji optymalizacji, słowa współczucia, w całości tylko to, co przysługuje.
- Asystent zaczyna każdą odpowiedź po stracie od zdania współczucia.

## 11. Przykładowe sprawy ZUS i zgodność z decyzjami

- **Wybór albo wgranie sprawy:** katalog 86 spraw pod numerami S01–S86 albo własny plik PDF lub zdjęcie.
- **Odczyt przez AI:** model przepisuje fakty ze skanów razem z numerami stron. Nie przepisuje imion, nazwisk, numerów PESEL ani adresów. Niczego nie liczy.
- **Potwierdzenie przez człowieka:** odczytane dane można poprawić i przeliczyć.
- **Ocena bez AI:** silnik sprawdza ubezpieczenie chorobowe w dniu powstania prawa, liczy podstawę z miesięcy z Z-3 krok po kroku i zestawia wynik z decyzją ZUS.
- **„Pokaż na osi”:** sprawa staje się planem.
- **Zgodność z decyzjami ZUS:** 53 z 59 spraw z jednoznacznym rozstrzygnięciem (77 z 86 spraw przeczytanych), policzone bez AI.
- **9 przykładowych rodzin** działa bez AI i bez skanów: jedno kliknięcie na ekranie startowym.

## 12. Asystent AI

- Prowadzi wywiad po jednym pytaniu. Treść i kolejność pytań ustala kod, nie model.
- Każdą odpowiedź zapisuje narzędziem. Narzędzie woła silnik i odsyła nową oś, a ekran podświetla, co się zmieniło.
- Odpowiada krótko: najpierw odpowiedź, najwyżej trzy zdania.
- Mówi o zasadach tylko z cytatem ze źródła. Na pytania spoza zakresu odpowiada, że aplikacja tego nie obejmuje.
- Umie zaproponować plany i przetestować plan, tymi samymi narzędziami co przyciski na ekranie.
- Sprawdzony na prawdziwym modelu na scenariuszach z ręcznie policzonymi datami: daty i kwoty zgadzały się we wszystkich turach.

## 13. Gdzie jest AI, a gdzie go nie ma

| Funkcja | AI? | Rola |
|---|---|---|
| Daty, wymiary urlopów, kwoty, prawo do zasiłku | nie | silnik reguł |
| Plany dla celu, test odporności, kalendarz wypłat | nie | silnik reguł |
| Sprawdzanie wniosku | nie | reguły; AI tylko przeredagowuje komunikaty na życzenie |
| Ocena przykładowej sprawy i zgodność z decyzjami ZUS | nie | silnik reguł |
| Asystent w czacie | tak | wywiad i wyjaśnienia, liczby z narzędzi |
| Odczyt sprawy ze skanu | tak | przepisanie faktów ze stronami, z potwierdzeniem człowieka |
| „Pismo z ZUS” | tak | wyjaśnienie prostym językiem z cytatami |
| Ilustracje | tak | wygenerowane grafiki okresów i zdarzeń |

Każda funkcja AI jest oznaczona w interfejsie. AI nigdy nie liczy kwot ani dat.

## 14. Symulacje integracji (oznaczone jako symulacja)

- Logowanie przez mObywatel: wybór metody, kod QR, konto testowe, zgoda.
- Dane z ZUS: ubezpieczenie, płatnik, podstawa.
- Zadłużenie składkowe i zaświadczenie na dzień powstania prawa do zasiłku. Kwota może przejść do planu, skutek opisuje silnik.
- Podgląd zwolnień e-ZLA.
- Zapytanie do PUE/eZUS.
- Wysyłka wniosku do pracodawcy albo ZUS z potwierdzeniem.
- Odpis aktu urodzenia.
- Odnośniki do ZUS, ministerstwa i Państwowej Inspekcji Pracy.

## 15. Panel administracyjny — zmiana przepisów bez programisty

- Edycja liczb ze źródłami: tygodnie urlopu macierzyńskiego, stawki zasiłku (100, 70, 81,5%), terminy wniosków.
- Nowa wersja obowiązuje od wybranej daty i wymaga podania podstawy zmiany.
- Podgląd skutków przed zapisem: oś przykładowej rodziny przed zmianą i po niej (okresy, terminy, dokumenty, kwoty).
- Historia wersji ze statusem.

## 16. Dostępność i urządzenia

- Jeden ekran planu dla telefonu i komputera.
- Prosty język: „dostaniesz”, „złóż do”.
- Większy tekst, tryb wysokiego kontrastu, widoczny fokus klawiatury, kontrast tekstu na poziomie WCAG AA.
- Animacje pokazują zmianę, nie zdobią. Aplikacja szanuje ustawienie ograniczenia ruchu.

## 17. Pokrycie wymagań z opisu wyzwania

| Wymaganie | Jak je spełniamy |
|---|---|
| a) świadczenia w ciąży, także brak uprawnień | zwolnienie w ciąży, utrata pracy, „nie przysługuje” z dalszą drogą, ryzyka |
| b) kalkulator dla obojga rodziców | oś z torami mamy i taty, kwoty za każdy okres |
| c) łączenie pracy z urlopem rodzicielskim | praca do pół etatu wydłuża urlop i zmienia kwotę |
| d) symulacja dla obojga rodziców | podział urlopu, plany dla celu, porównanie stawek |
| e), j) adopcja i rodzina zastępcza | osobna oś dla dziecka przyjętego na wychowanie |
| f) indywidualna podstawa wymiaru | podstawa z Z-3 krok po kroku, przykładowe sprawy |
| g) dokumenty, terminy, gdzie złożyć | wnioski na osi, PDF, sprawdzanie, kalendarz |
| h) zagrożenia i ryzyka | „Na co uważać”, test odporności, punkty bez powrotu |
| symulacje integracji | mObywatel, dane ZUS, zadłużenie, e-ZLA, PUE/eZUS, wysyłka, akt urodzenia |
| zmiana parametrów | panel administracyjny z wersjami od daty |
| wgranie albo wybór wniosków | przykładowe sprawy: ubezpieczenie i wyliczenia obok decyzji ZUS |

## 18. Dlaczego można temu ufać

- Ponad 2 500 testów automatycznych. Oczekiwane daty i kwoty są w nich policzone ręcznie.
- Każdy cytat jest sprawdzany co do znaku i co do strony.
- Niezależna weryfikacja reguł z dokumentami ZUS, sekcja po sekcji.
- Asystent sprawdzany na prawdziwym modelu na scenariuszach z ręcznie policzonym wynikiem.
- Zgodność z decyzjami ZUS na przykładowych sprawach: 53 z 59 spraw z jednoznacznym rozstrzygnięciem.

## 19. Technologia

- Demo online: https://przewodnik-rodzica.up.railway.app (jeden kontener, backend serwuje też stronę).

- Frontend: React, TypeScript, Vite, Tailwind, Motion.
- Backend: Python, FastAPI. Silnik reguł to czysty, deterministyczny moduł bez bazy i bez AI.
- Asystent: Pydantic AI, model Claude. Dokumenty czyta Claude albo Gemini.
- Baza: Supabase (rozmowy i wersje parametrów).
- Jedna warstwa nad dostawcą modelu, więc model można podmienić.

## 20. Co dalej

- Zgodność na wszystkich 86 sprawach.
- Wersje językowe: angielska i ukraińska.
- Głos: czytanie wyniku na głos i pytania głosem.
- Zanonimizowana informacja zwrotna dla ZUS: na którym pytaniu rodzice kończą, co ich zaskakuje.
- Ścieżka z modelem uruchamianym lokalnie.
