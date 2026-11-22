# Eval: the assistant and the timeline against the documents

End-to-end checks of the chat with the **real language model**: onboarding → the assistant's
welcome (`timeline_ready`) → answers and changes in the chat. After every step the harness
compares the timeline with dates computed by hand from the Przewodnik and the Labour Code, and
the assistant's reply with the timeline and the sources.

**It costs money.** Every step is one chat turn (one model run with several requests). The full
suite is 122 turns (`--only` runs a part). It is **not part of CI**: run it by hand after
changing prompts, tools, the model or the engine.

## Running

Start a backend with Supabase switched off, so no test session reaches the hosted database:

```bash
cd backend
SUPABASE_URL= SUPABASE_SECRET_KEY= uv run uvicorn app.main:app --port 8010
```

Then, in another terminal:

```bash
cd backend
uv run python ../tools/eval/run.py --base http://127.0.0.1:8010 --out /tmp/eval.json
uv run python ../tools/eval/run.py --only twins-and-back,leave-before-birth --runs 3
uv run python ../tools/eval/run.py --rescore /tmp/eval.json      # re-check, no LLM calls
```

Options: `--only` (comma-separated scenario ids), `--runs` (override runs per scenario),
`--parallel` (sessions at once, default 4), `--out` (every turn: reply, tool calls, timelines
before and after, checks, time and tokens), `--label` (the chat model the backend runs, saved in
`--out`), `--rescore` (apply the current checks to a saved `--out` file), `--compare` (several
saved `--out` files side by side, no LLM calls). The exit code is 1 when any step has a hard
failure.

## Time, tokens and cost (ZADANIA B.17)

Every turn ends with a `done` event that carries the server's measurement (`usage`: time to the
first text and of the whole turn, requests, input tokens including cached ones, tokens read from
and written to the prompt cache, output tokens, cost from genai-prices). The backend also logs it
as one `chat turn {…}` line, without any conversation content. After the checks the harness
prints, per scenario: the median time to the first text (measured by the harness, including the
interview question the server adds), the median turn time, input / cached / output tokens,
input tokens per turn, cost, and in how many turns after the first the prompt cache was read
(`cache from 2nd turn`: with a working cache that is every later turn).

Offline, without a model, `prompt_size.py` measures what the model gets per turn (instructions,
tool definitions, history) for representative interview states and a 5-turn conversation:

```bash
cd backend
uv run python ../tools/eval/prompt_size.py
uv run python ../tools/eval/prompt_size.py --backend /path/to/old/backend   # e.g. git archive
```

## Comparing chat models

One backend per model (the same port, one after another), then the same scenarios, then the
comparison. Gemini needs `GEMINI_API_KEY`, Claude `ANTHROPIC_API_KEY` (or OpenRouter with
`LLM_PROVIDER=openrouter` and `anthropic/claude-sonnet-5.5` / `anthropic/claude-haiku-5.5`):

```bash
cd backend
# terminal 1, for each model in turn:
SUPABASE_URL= SUPABASE_SECRET_KEY= LLM_PROVIDER=google LLM_MODEL=gemini-flash-latest \
  uv run uvicorn app.main:app --port 8010
SUPABASE_URL= SUPABASE_SECRET_KEY= LLM_PROVIDER=anthropic LLM_MODEL=claude-sonnet-5-5 \
  uv run uvicorn app.main:app --port 8010
SUPABASE_URL= SUPABASE_SECRET_KEY= LLM_PROVIDER=anthropic LLM_MODEL=claude-haiku-5-5 \
  uv run uvicorn app.main:app --port 8010
# terminal 2, after each start:
uv run python ../tools/eval/run.py --label gemini-flash-latest --out /tmp/eval-gemini-flash.json
uv run python ../tools/eval/run.py --label claude-sonnet-5-5 --out /tmp/eval-sonnet-5-5.json
uv run python ../tools/eval/run.py --label claude-haiku-5-5 --out /tmp/eval-haiku-5-5.json
# the table: steps without hard failures, medians of time, input tokens per turn, cost
uv run python ../tools/eval/run.py --compare /tmp/eval-*.json
```

`--runs 1` halves the cost of a first look; the determinism table needs the default runs.

The expected dates assume the server's "today" is **2026-11-21** (due dates must lie ahead,
birth dates behind). On another day the harness warns; shift all dates in `scenarios.py` by the
same number of days.

## What is checked

Per step (`checks.py`, `run.py`):

- **Timeline**: periods, days and documents equal the hand-computed values (`scenarios.py`,
  each with its rule: KP art. 180 § 1, 180¹, 180², 182¹ᵃ, 182³, 183¹; Przewodnik s. 4–8);
  removed elements are gone; explanation points present or absent.
- **Dependencies**: the right tool with the right arguments; the changed elements and the
  changed explanation points are reported (`changed`, `changed_notes`); the stream equals what
  `GET /api/session/{id}` restores.
- **Reply against the timeline**: every date in the reply exists on the timeline (or in the
  user's message, the previous timeline or the sources); the key new dates and numbers are
  stated; required/forbidden phrases (e.g. a source like `art. 180 § 1`, no "40 tyg.").
- **Explanation**: the welcome covers the opening points (the case, the main entitlement or
  risk, a loss; `opening_note_ids`), not all of "Twoja sytuacja"; after a change, the changed
  points are reported softly (the chat says what the change means, not every point).
- **Brevity**: a reply without the interview question is at most 600 characters (soft after a
  loss), so the chat never becomes a wall of text.
- **Quotes**: every „…” of 4+ words is a literal fragment of `przewodnik_pages.json` or
  `kodeks_pracy.json` (an elision must be marked with […]) and the parenthesis after it names a
  page or article that contains it. A non-literal quote is classified: the app's own explanation
  text presented as a source, or an altered quote.
- **Interview**: no scenario change on the welcome turn or on out-of-scope questions (the
  assistant must not record answers nobody gave); the reply ends with the next interview
  question word for word; the next question key.
- **Tone**: after a loss: no "!", sympathy, no congratulations; out of scope: says so; no
  internal instructions leak into the reply.

Hard checks fail a step; soft ones (repeating unchanged dates, not re-asking the question after
a mere question) are warnings.

**Determinism**: scenarios with `runs > 1` are compared step by step across fresh sessions:
the timeline JSON hash, the tool calls, wrong dates, and which dates and week counts each run
states (wording may differ, facts may not).

## Adding a scenario

Add a dict to `SCENARIOS` in `scenarios.py`: `onboarding` (the `PUT /api/session/{id}/onboarding`
body) and `steps` (`say` or `event`, plus the expectations described at the top of the file). A
step with `patch` first changes the scenario the way the app does without the chat
(`PATCH /api/session/{id}/scenario`, e.g. the week tiles or the 81,5% switch), which leaves a
hidden note in the history (`app-change-note`); `no_setters` fails the step on any `set_*` call.
Compute expected dates by hand from the documents and write the rule next to them; never copy
them from the engine. Do not put text from the confidential materials into scenarios: short
references like "KP art. 180 § 1" are enough.
