# Claim Assessor

FastAPI backend: submit one insurance claim, get a recommendation (`APPROVE`, `REJECT`, or `REQUEST_MORE_INFO`) and a cited report.

No frontend. Demo with curl or [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Gemini gathers evidence through four tools. Business rules decide the claim. Gemini writes the reasoning, which is checked before the report is returned.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- A Gemini API key (`GEMINI_API_KEY`)

## Setup

```bash
uv sync
cp .env.example .env   # set GEMINI_API_KEY
```

The example also sets `GEMINI_MODEL=gemini-3.5-flash-lite`.

## Run

```bash
uv run uvicorn claim_assessor.main:app --reload
```

`GET /health` → `{"status":"ok"}`.

## Cases

Request bodies are the files in `test_cases/`. `POST /assessments` waits for the finished report.

| File | Recommendation |
| --- | --- |
| `test_cases/approve.json` | `APPROVE` |
| `test_cases/reject.json` | `REJECT` |
| `test_cases/request_more_info.json` | `REQUEST_MORE_INFO` |

## API

### Assess a claim

```bash
curl -s -X POST http://127.0.0.1:8000/assessments \
  -H 'Content-Type: application/json' \
  -d @test_cases/approve.json
```

`201`:

```json
{
  "assessment_id": "…",
  "claim_id": "CLAIM-001",
  "report": {
    "recommendation": "APPROVE",
    "missing_documents": [],
    "policy_citations": ["COVERAGE-001", "BENEFIT-LIMIT-001", "COINSURANCE-001"]
  },
  "markdown": "…",
  "tool_calls": [],
  "created_at": "…"
}
```

`report` also includes document review, policy verification, medical necessity, benefit calculation, findings, and reasoning. `tool_calls` lists every call, including rejected ones.

Invalid body → `422`. Gemini failure, or a report still invalid after one retry → `502` with `{"detail":"Assessment could not be completed"}`.

### Read a stored assessment

```bash
curl -s http://127.0.0.1:8000/assessments/{assessment_id}
```

Unknown id → `404`.

### Ask a follow-up

```bash
curl -s -X POST http://127.0.0.1:8000/assessments/{assessment_id}/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why was this claim approved?"}'
```

```json
{ "answer": "…" }
```

The answer uses only the stored assessment. A question must be 1–2000 characters; otherwise `422`.

Assessments are **in memory**. Restarting uvicorn drops them.

## How a decision is made

1. **Evidence.** Gemini calls `verifyDocument` once for every submitted document, then `lookupPolicy`, `checkMedicalNecessity`, and `calculateBenefit`. Code checks order and arguments before each call runs. A rejected call goes back to the model as an error. The loop stops at 20 calls.
2. **Decision.** `assessment/rules.py` decides. `REJECT` (inactive policy, outside coverage, member not covered, waiting period, exclusion, unsupported claim type) outranks `REQUEST_MORE_INFO` (bad or missing documents, type mismatch, unresolved medical necessity), which outranks `APPROVE`.
3. **Report.** Facts and the recommendation come from the tools and the rules. The model writes reasoning and citations only. Citations must exist in the policy and cover every finding. An invalid draft is sent back once; a second failure is `502`.

| Tool | Purpose | Checked before it runs |
| --- | --- | --- |
| `verifyDocument` | One submitted document | Each submitted document exactly once, before the other tools |
| `lookupPolicy` | Policy terms and clauses | Policy id matches the claim |
| `checkMedicalNecessity` | Diagnosis and procedure codes | Codes match the claim |
| `calculateBenefit` | Covered amount and member responsibility | Amount and claim type match the claim |

## System prompts

Defined in `infrastructure/gemini.py`.

Tool calling:

```text
You are an insurance claim assessor gathering evidence for one claim.
Call the tools in this order: verifyDocument once for every submitted document,
then lookupPolicy, checkMedicalNecessity, and calculateBenefit.
Copy argument values exactly from the claim. If a tool returns an error, fix the call.
```

Report:

```text
You write the reasoning section of a claim assessment report.
The recommendation was already decided by deterministic rules; do not change it.
Explain each decision finding in one plain sentence, using only the evidence provided.
Cite only clause ids that exist in the policy, and cite every clause id in the findings.
If validation_errors is not empty, fix every listed problem.
```

Follow-up question:

```text
Answer the reviewer's question about a claim assessment.
Use only the assessment record provided. If the record does not contain the answer, say so.
Cite policy clause ids when they support the answer.
```

## Tests

```bash
make check
uv run python evals/run.py [case ...]
```

`make check` runs the format check, lint, mypy, and unit tests. Unit tests use a fake LLM and do not touch the network. See `tests/README.md` for what each file covers.

`evals/run.py` calls real Gemini, checks `evals/expected.json`, and writes `outputs/<case>/` (`report.json`, `report.md`, `tool_calls.jsonl`). One case takes 7–8 requests.

A real Gemini run of the three cases:

| Case | Recommendation | Missing documents | Citations |
| --- | --- | --- | --- |
| `approve` | `APPROVE` | none | BENEFIT-LIMIT-001, COINSURANCE-001, COVERAGE-001 |
| `reject` | `REJECT` | none | EXCLUSION-COSMETIC-001 |
| `request_more_info` | `REQUEST_MORE_INFO` | discharge_summary | COVERAGE-001, REQUIRED-DOCUMENTS-001 |

## Architecture

```text
Client → FastAPI → AssessmentService
                      ├─ AssessmentAgent
                      │    ├─ GeminiClient        (tool calls, then the report draft)
                      │    ├─ tools               (reference data in data/)
                      │    └─ rules.decide        (the recommendation)
                      └─ InMemoryAssessmentRepository
```

- The API validates the body and maps errors to status codes. It does not decide the claim.
- The agent lets Gemini choose each tool call. Code rejects a call that skips a document, runs out of order, or changes the amount or claim type.
- `rules.decide` owns the recommendation. The model writes reasoning and citations.
- Concrete classes are wired in `main.py` (`create_app`, `build_assessment_service`).

```text
src/claim_assessor/
  main.py            composition root
  api/               routers, schemas, error mapping
  assessment/        models, tools, rules, agent, report, service
  infrastructure/    JSON reference data, Gemini, in-memory repository
```

## Data

- `data/policies.json` — three synthetic policies.
- `data/documents.json` — submitted documents, already extracted.
- `data/medical_rules.json` — medical-necessity rules.
- `test_cases/` — the three claims above.

## Known limitations

- Assessments are process-local. Restart loses them; workers do not share them.
- No authentication or rate limiting on the API.
- No OCR. Documents in `data/` are pre-extracted text.
- One assessment uses 7–8 Gemini requests. The free tier is rate-limited (15 requests per minute was observed), so running all three cases back to back can return 429; the API maps that to 502.

## AI usage

About 8.5 hours over two days (Oct 16 evening and Oct 17), from the timestamps in `docs/ai-conversation.md`.

Cursor implemented the code. Design and review stayed on my side. Places I corrected the assistant (chat numbers are in that log):

- **Over-engineering (Chat 3).** The first plan had 38 tests before any feature worked. I rejected it and switched to a vertical slice, with tests only for high-risk behavior.
- **Hardcoded clause ids (Chat 8).** Benefit calculation cited fixed clause ids. Citations now come from the policy's own clauses.
- **Invented business rule (Chat 12).** A validator required exactly one clause per type. That rule is not in the requirement, so citations are optional and a finding with no clause renders as `no policy clause`.

The Gemini key lives only in the git-ignored `.env`. No key appears in the conversation log or the repository.

`docs/ai-conversation.md` is every Cursor agent chat for this challenge, ordered by start time. User messages are verbatim, assistant replies are included as written, and tool calls are one-line summaries. It was exported from Cursor's local transcripts.
