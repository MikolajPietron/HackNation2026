# Zasiłkowy Przewodnik Przyszłego Rodzica

Projekt na HackNation 2026, wyzwanie ZUS. Aplikacja buduje rodzicom osobistą **oś czasu**: jakie świadczenia im przysługują, ile pieniędzy dostaną, kto płaci, jakie wnioski złożyć i do kiedy, jakie prawa ich chronią. Pokazuje też, jak zdarzenia wpływają na siebie nawzajem (wcześniak, bliźnięta, hospitalizacja…).

Produkt, domena i zasady pracy: [CLAUDE.md](CLAUDE.md).

## Stack

- **Backend**: Python 3.13, FastAPI, uv — `backend/`
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS — `frontend/`
- **Baza**: Supabase (Postgres), migracje SQL w `supabase/migrations/`
- **Asystent AI**: Pydantic AI + Claude (przez OpenRouter) — rozmowa zbiera datę porodu i inne fakty, a narzędzia agenta zmieniają oś czasu. Daty liczy deterministyczny silnik reguł, nie AI.

## Wymagania

- Node.js 24 (minimum 20.19) i npm
- [uv](https://docs.astral.sh/uv/) — sam pobierze Pythona 3.13
- Docker — tylko do lokalnej bazy Supabase

## Start

```bash
npm run setup                          # zależności: frontend, CLI Supabase, backend
cp backend/.env.example backend/.env   # uzupełnij klucze
npm run dev                            # API na :8000 + frontend na :5173
```

Otwórz http://localhost:5173 i podaj w czacie datę porodu. Czat potrzebuje klucza LLM w `backend/.env` (domyślnie `OPENROUTER_API_KEY`; Claude przez OpenRouter); bez klucza zwraca komunikat o wyłączonym asystencie. Kalkulator działa bez AI pod `POST /api/timeline` (dokumentacja API: http://localhost:8000/docs).

## Komendy

| Komenda | Co robi |
|---|---|
| `npm run dev` | backend (FastAPI, :8000) i frontend (Vite, :5173) naraz |
| `npm run dev:api`, `npm run dev:web` | to samo osobno |
| `npm test` | testy backendu (pytest) |
| `npm run lint` | ruff, oxlint i sprawdzenie typów TypeScript |
| `npm run format` | formatowanie backendu (ruff) |
| `npm run build` | build frontendu |
| `npm run db:start`, `db:stop`, `db:status` | lokalny Supabase w Dockerze |
| `npm run db:migration <nazwa>` | nowa migracja SQL |
| `npm run db:reset` | odtworzenie lokalnej bazy z migracji i `seed.sql` |
| `npm run data:zus` | przygotowanie danych ZUS: OCR i katalog spraw (macOS, tesseract, poppler) |

## Struktura

```
backend/         FastAPI: app/api (REST), app/engine (silnik reguł), app/services (Supabase, Claude), tests/
frontend/        React + Vite + Tailwind
supabase/        config.toml, migrations/, seed.sql
tools/zus-data/  pipeline danych ZUS (OCR, poprawa obróconych stron, katalog spraw)
docs/            opis wyzwania (Przewodnik_Rodzica_ZUS.pdf); dokumentyZUS/ jest poufne i poza gitem
```

## Dane od ZUS

Materiały i przykładowe sprawy od ZUS trzymamy lokalnie w `docs/dokumentyZUS/` (katalog jest w `.gitignore`). Nie wolno ich kopiować ani rozpowszechniać. Nie commituj ich i nie wysyłaj do hostowanego Supabase ani zewnętrznych API bez zgody mentorów ZUS.
