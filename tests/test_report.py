from claim_assessor.assessment.models import ReportDraft
from claim_assessor.assessment.report import build_report, render_markdown, validate_draft
from claim_assessor.assessment.rules import decide
from claim_assessor.infrastructure.reference_data import ReferenceData
from tests.fakes import ScriptedLLM, collect_evidence, load_claim


def render(reference_data: ReferenceData, case: str) -> str:
    evidence = collect_evidence(reference_data, load_claim(case))
    decision = decide(evidence)
    draft = ScriptedLLM().draft_report(evidence, decision, [])
    return render_markdown(build_report(evidence, decision, draft))


def test_draft_must_cite_required_clauses_and_only_real_ones(
    reference_data: ReferenceData,
) -> None:
    evidence = collect_evidence(reference_data, load_claim("request_more_info"))
    decision = decide(evidence)
    draft = ReportDraft(reasoning=["Documents are missing."], policy_citations=["FAKE-999"])

    errors = validate_draft(evidence, decision, draft)

    assert errors == [
        "Cited clauses do not exist in the policy: ['FAKE-999']",
        "Required clauses are not cited: ['COVERAGE-001', 'REQUIRED-DOCUMENTS-001']",
    ]


def test_report_lists_missing_document_and_cites_each_reason(
    reference_data: ReferenceData,
) -> None:
    markdown = render(reference_data, "request_more_info")

    assert "- discharge_summary: **missing**" in markdown
    assert "- Missing discharge_summary [`REQUIRED-DOCUMENTS-001`]" in markdown


def test_report_shows_claim_type_not_included(reference_data: ReferenceData) -> None:
    markdown = render(reference_data, "reject")

    assert "- Claim type included: False" in markdown
