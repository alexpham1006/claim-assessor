from datetime import date

import pytest

from claim_assessor.assessment.models import (
    CoveragePeriod,
    DocumentStatus,
    Finding,
    Recommendation,
    WaitingPeriod,
)
from claim_assessor.assessment.rules import decide
from claim_assessor.infrastructure.reference_data import ReferenceData
from tests.fakes import collect_evidence, load_claim


def messages(findings: list[Finding]) -> list[str]:
    return [finding.message for finding in findings]


def test_decide_rejects_excluded_procedure(reference_data: ReferenceData) -> None:
    evidence = collect_evidence(reference_data, load_claim("reject"))

    decision = decide(evidence)

    assert decision.recommendation is Recommendation.REJECT
    assert "EXCLUSION-COSMETIC-001" in decision.required_citations


@pytest.mark.parametrize(
    ("policy_update", "reason"),
    [
        pytest.param({"status": "lapsed"}, "Policy is lapsed", id="inactive-policy"),
        pytest.param(
            {
                "coverage_period": CoveragePeriod(
                    start_date=date(2020, 1, 1), end_date=date(2020, 12, 31)
                )
            },
            "Treatment is outside coverage period",
            id="outside-coverage-period",
        ),
        pytest.param(
            {"waiting_period": WaitingPeriod(months=3, satisfied=False)},
            "Waiting period is not satisfied",
            id="waiting-period",
        ),
    ],
)
def test_decide_rejects_when_policy_does_not_cover_the_claim(
    reference_data: ReferenceData, policy_update: dict[str, object], reason: str
) -> None:
    evidence = collect_evidence(reference_data, load_claim("approve"))
    policy = evidence.policy.model_copy(update=policy_update)

    decision = decide(evidence.model_copy(update={"policy": policy}))

    assert decision.recommendation is Recommendation.REJECT
    assert reason in messages(decision.findings)


def test_decide_rejects_unknown_claim_type(reference_data: ReferenceData) -> None:
    claim = load_claim("approve").model_copy(update={"claim_type": "unknown"})

    decision = decide(collect_evidence(reference_data, claim))

    assert decision.recommendation is Recommendation.REJECT
    assert "Claim type unknown is not included" in messages(decision.findings)


def test_decide_keeps_finding_uncited_when_policy_has_no_matching_clause(
    reference_data: ReferenceData,
) -> None:
    claim = load_claim("reject").model_copy(update={"member_id": "MEMBER-999"})

    decision = decide(collect_evidence(reference_data, claim))

    assert decision.recommendation is Recommendation.REJECT
    assert Finding(None, "Member is not on the policy") in decision.findings


def test_decide_requests_missing_document_and_clinical_review(
    reference_data: ReferenceData,
) -> None:
    evidence = collect_evidence(reference_data, load_claim("request_more_info"))

    decision = decide(evidence)

    assert decision.recommendation is Recommendation.REQUEST_MORE_INFO
    assert Finding("REQUIRED-DOCUMENTS-001", "Missing discharge_summary") in decision.findings
    assert any(
        message.startswith("Clinical review required") for message in messages(decision.findings)
    )


@pytest.mark.parametrize(
    ("document_update", "reason"),
    [
        pytest.param(
            {"document_type": "unrecognized"}, "DOC-001 has type unrecognized", id="wrong-type"
        ),
        pytest.param(
            {"status": DocumentStatus.INCOMPLETE, "issues": ["missing signature"]},
            "DOC-001 is incomplete: missing signature",
            id="incomplete",
        ),
    ],
)
def test_decide_requests_info_when_a_document_is_not_usable(
    reference_data: ReferenceData, document_update: dict[str, object], reason: str
) -> None:
    evidence = collect_evidence(reference_data, load_claim("approve"))
    first, *others = evidence.documents
    documents = [first.model_copy(update=document_update), *others]

    decision = decide(evidence.model_copy(update={"documents": documents}))

    assert decision.recommendation is Recommendation.REQUEST_MORE_INFO
    assert any(message.startswith(reason) for message in messages(decision.findings))
