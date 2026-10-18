import json
import logging
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from claim_assessor.api.schemas import AssessmentResponse
from claim_assessor.assessment.models import Claim
from claim_assessor.config import get_settings
from claim_assessor.main import build_assessment_service

ROOT = Path(__file__).parents[1]

logger = logging.getLogger("evals")


def main(case_names: Sequence[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    expected = json.loads((ROOT / "evals" / "expected.json").read_text())
    service = build_assessment_service(get_settings())
    fixtures = sorted((ROOT / "test_cases").glob("*.json"))
    for fixture in [f for f in fixtures if not case_names or f.stem in case_names]:
        claim = Claim.model_validate_json(fixture.read_bytes())
        response = AssessmentResponse.from_domain(service.create_assessment(claim))
        _validate_result(fixture.stem, expected[fixture.stem], claim, response)
        destination = ROOT / "outputs" / fixture.stem
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "report.json").write_text(response.report.model_dump_json(indent=2))
        (destination / "report.md").write_text(response.markdown)
        (destination / "tool_calls.jsonl").write_text(
            "".join(f"{call.model_dump_json()}\n" for call in response.tool_calls)
        )
        rejected = sum(call.error is not None for call in response.tool_calls)
        logger.info(
            "%s: %s (%d tool calls, %d rejected)",
            fixture.stem,
            response.report.recommendation,
            len(response.tool_calls),
            rejected,
        )


def _validate_result(
    case_name: str, expected: dict[str, Any], claim: Claim, response: AssessmentResponse
) -> None:
    report = response.report
    if str(report.recommendation) != expected["recommendation"]:
        raise AssertionError(f"{case_name}: unexpected recommendation")
    benefit = report.benefit_calculation
    if benefit.covered_amount != Decimal(expected["covered_amount"]):
        raise AssertionError(f"{case_name}: unexpected covered amount")
    if benefit.member_responsibility != Decimal(expected["member_responsibility"]):
        raise AssertionError(f"{case_name}: unexpected member responsibility")

    actual_document_statuses = {
        document.document_id: document.status for document in report.document_review
    }
    if actual_document_statuses != expected["document_statuses"]:
        raise AssertionError(f"{case_name}: unexpected document statuses")
    if report.missing_documents != expected["missing_document_types"]:
        raise AssertionError(f"{case_name}: unexpected missing documents")
    if not set(expected["policy_citations"]).issubset(report.policy_citations):
        raise AssertionError(f"{case_name}: missing expected policy citation")

    expected_tools = ["verifyDocument"] * len(claim.submitted_documents) + [
        "lookupPolicy",
        "checkMedicalNecessity",
        "calculateBenefit",
    ]
    actual_tools = [call.tool for call in response.tool_calls]
    if actual_tools != expected_tools:
        raise AssertionError(f"{case_name}: unexpected tool trace")
    # Accepted calls already passed EvidenceCollector.check_call, which pins exact arguments.
    if any(call.error is not None for call in response.tool_calls):
        raise AssertionError(f"{case_name}: rejected tool call in trace")


if __name__ == "__main__":
    main(sys.argv[1:])
