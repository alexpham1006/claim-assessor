# Tests

Unit and API tests for the claim assessment service. They run offline: no network,
no real LLM. Real Gemini runs live in `evals/run.py`.

## Run

```bash
make test                                       # all unit tests
uv run pytest tests/test_rules.py -x            # one file
uv run pytest "tests/test_agent.py::test_agent_fails_when_tool_call_limit_is_exceeded"
```

## What each file covers

| File | Covers | Main risk it guards |
|------|--------|---------------------|
| `test_api.py` | HTTP endpoints end to end with a fake LLM | Status codes, request validation (422), not found (404), LLM failure (502) |
| `test_agent.py` | `AssessmentAgent.run` | Bad tool calls are rejected and the run still completes; tool-call limit; report retry |
| `test_rules.py` | `rules.decide` | APPROVE / REJECT / REQUEST_MORE_INFO and the finding behind each |
| `test_tools.py` | Tool handlers | Money: covered amount, coinsurance, remaining limit; medical fallback |
| `test_report.py` | `report.validate_draft` | LLM citations must exist and cover every finding |
| `test_config.py` | `Settings` | Env is read and the API key is never printed |

## Shared helpers

- `conftest.py` provides the `reference_data` fixture backed by `data/`.
- `fakes.py`:
  - `load_claim(name)` loads a claim from `test_cases/<name>.json`.
  - `collect_evidence(reference_data, claim)` runs the four tools correctly and returns
    `Evidence`, so rule and report tests can start from realistic input.
  - `correct_tool_calls(claim)` is the expected tool sequence for a claim.
  - `ScriptedLLM` is a well-behaved fake `LLMClient`. Tests subclass it to inject one
    specific misbehavior (see `OneBadCallLLM`, `StuckLLM`, `DraftsInvalidReportLLM`
    in `test_agent.py`).

## Conventions

- Name tests `test_<unit>_<behavior>[_when_<condition>]`; the name should read as the
  rule being protected.
- Arrange / Act / Assert, separated by blank lines.
- Start from a real test case and change only what the test is about, using
  `model_copy` on immutable models. Do not mutate internal state of objects under test.
- Test behavior through the public entry point (`agent.run`, `decide`, the HTTP API),
  not private helpers.
- Use `pytest.param(..., id="...")` for parametrized cases so failures name the case.
- Test what can break and matters: money, decisions, LLM boundaries, input validation.
  Do not add tests that only re-read data.
