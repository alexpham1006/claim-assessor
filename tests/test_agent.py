from collections.abc import Sequence

import pytest

from claim_assessor.assessment.agent import MAX_TOOL_CALLS, AssessmentAgent
from claim_assessor.assessment.llm import ToolCall, Turn
from claim_assessor.assessment.models import Claim, Decision, Evidence, Recommendation, ReportDraft
from claim_assessor.assessment.tools import Tool
from claim_assessor.errors import AssessmentFailedError
from claim_assessor.infrastructure.reference_data import ReferenceData
from tests.fakes import ScriptedLLM, correct_tool_calls, load_claim

INVALID_DRAFT = ReportDraft(reasoning=["Looks fine."], policy_citations=["FAKE-999"])


class OneBadCallLLM(ScriptedLLM):
    def __init__(self, bad_call: ToolCall, before: str) -> None:
        self._bad_call = bad_call
        self._before = before

    def next_tool_call(self, conversation: Sequence[Turn], tools: Sequence[Tool]) -> ToolCall:
        script = correct_tool_calls(Claim.model_validate_json(str(conversation[0])))
        position = next(i for i, call in enumerate(script) if call.name == self._before)
        script.insert(position, self._bad_call)
        return script[sum(isinstance(turn, ToolCall) for turn in conversation)]


class StuckLLM(ScriptedLLM):
    def next_tool_call(self, conversation: Sequence[Turn], tools: Sequence[Tool]) -> ToolCall:
        return ToolCall("deleteClaim", {})


class DraftsInvalidReportLLM(ScriptedLLM):
    def __init__(self, invalid_drafts: int) -> None:
        self._invalid_drafts = invalid_drafts
        self.received_errors: list[list[str]] = []

    def draft_report(
        self, evidence: Evidence, decision: Decision, validation_errors: Sequence[str]
    ) -> ReportDraft:
        self.received_errors.append(list(validation_errors))
        if len(self.received_errors) <= self._invalid_drafts:
            return INVALID_DRAFT
        return super().draft_report(evidence, decision, validation_errors)


@pytest.mark.parametrize(
    ("bad_call", "before", "reason"),
    [
        pytest.param(
            ToolCall("lookupPolicy", {"policy_id": "POLICY-001"}),
            "verifyDocument",
            "Call verifyDocument next",
            id="wrong-order",
        ),
        pytest.param(
            ToolCall("verifyDocument", {"document_id": "DOC-999"}),
            "verifyDocument",
            "document_id must be one of",
            id="unsubmitted-document",
        ),
        pytest.param(
            ToolCall(
                "calculateBenefit",
                {"policy_id": "POLICY-001", "claim_type": "hospitalization", "amount": "99"},
            ),
            "calculateBenefit",
            "Use the claim values",
            id="altered-amount",
        ),
        pytest.param(ToolCall("deleteClaim", {}), "verifyDocument", "unknown tool", id="unknown"),
    ],
)
def test_agent_rejects_bad_tool_call_and_still_completes(
    reference_data: ReferenceData, bad_call: ToolCall, before: str, reason: str
) -> None:
    agent = AssessmentAgent(reference_data, OneBadCallLLM(bad_call, before))

    result = agent.run(load_claim("approve"))

    rejected = [call for call in result.tool_calls if call.error is not None]
    assert len(rejected) == 1
    assert reason in str(rejected[0].error)
    assert result.report.recommendation is Recommendation.APPROVE


def test_agent_fails_when_tool_call_limit_is_exceeded(reference_data: ReferenceData) -> None:
    agent = AssessmentAgent(reference_data, StuckLLM())

    with pytest.raises(AssessmentFailedError, match=str(MAX_TOOL_CALLS)):
        agent.run(load_claim("approve"))


def test_agent_retries_report_with_validation_errors(reference_data: ReferenceData) -> None:
    llm = DraftsInvalidReportLLM(invalid_drafts=1)

    result = AssessmentAgent(reference_data, llm).run(load_claim("approve"))

    assert any("FAKE-999" in error for error in llm.received_errors[1])
    assert "FAKE-999" not in result.report.policy_citations


def test_agent_fails_when_report_stays_invalid(reference_data: ReferenceData) -> None:
    agent = AssessmentAgent(reference_data, DraftsInvalidReportLLM(invalid_drafts=2))

    with pytest.raises(AssessmentFailedError, match="Report failed validation"):
        agent.run(load_claim("approve"))
