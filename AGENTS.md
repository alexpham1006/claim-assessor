# Claim Assessor

Python 3.11+ FastAPI service for AI Challenge 11: a Gemini agent assesses insurance claims.

## Commands (use these, do not invent others)

| Task | Command |
|------|---------|
| Install | `uv sync` |
| Format + autofix | `make fmt` |
| Full gate (format check, lint, mypy, tests) | `make check` |
| Unit tests only | `make test` |
| Single test | `uv run pytest tests/path.py::test_name -x` |
| Add dependency | `uv add <pkg>` (dev: `uv add --group dev <pkg>`) |

## Layout

```
src/claim_assessor/         application code (src layout; import as `claim_assessor.*`)
  main.py           composition root: create_app, wiring only
  config.py         Settings (pydantic-settings). The only place that reads env vars.
  api/              HTTP layer: routers, schemas, domain-error -> status mapping
  assessment/       domain + use cases; depends on no web framework or provider SDK
  infrastructure/   adapters: reference data files, Gemini, persistence
tests/              unit tests with tests/fakes.py; never call a real LLM
evals/run.py        real-LLM run over test_cases/, writes outputs/
docs/               ai-conversation.md (AI conversation log for the submission)
.cursor/            rules and hooks for Cursor
```

## Conventions

- Language: chat with the user in Vietnamese; code, comments, commits, docs in English.
- Style lives in `.cursor/rules/`; do not duplicate it here.
- Commits: Conventional Commits. Never commit or push unless explicitly asked.

## Gotchas

- Config comes from provider-standard env vars / `.env` (for example `GEMINI_API_KEY`).
  `.env` is git-ignored and blocked by `.cursorignore`; add new keys to `.env.example`.
- Unit tests must not touch the network or a real LLM. Use a fake client.
- Gemini free tier is rate-limited: `evals/run.py` takes 7-8 requests per case.
