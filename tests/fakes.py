from collections.abc import Sequence
from pathlib import Path

from claim_assessor.assessment.agent import EvidenceCollector
from claim_assessor.assessment.llm import ToolCall, Turn
from claim_assessor.assessment.models import Assessment, Claim, Decision, Evidence, ReportDraft
from claim_assessor.assessment.tools import TOOLS, Tool
from claim_assessor.infrastructure.reference_data import ReferenceData


def load_claim(name: str) -> Claim:
    return Claim.model_validate_json(Path("test_cases", f"{name}.json").read_bytes())


def collect_evidence(reference_data: ReferenceData, claim: Claim) -> Evidence:
    collector = EvidenceCollector(claim=claim)
    for call in correct_tool_calls(claim):
        tool = TOOLS[call.name]
        collector.add(tool.handler(reference_data, tool.args_model.model_validate(call.arguments)))
    return collector.to_evidence()


def correct_tool_calls(claim: Claim) -> list[ToolCall]:
    return [
        *(
            ToolCall("verifyDocument", {"document_id": document.document_id})
            for document in claim.submitted_documents
        ),
        ToolCall("lookupPolicy", {"policy_id": claim.policy_id}),
        ToolCall(
            "checkMedicalNecessity",
            {
                "diagnosis_code": claim.diagnosis_code,
                "procedure_codes": claim.procedure_codes,
            },
        ),
        ToolCall(
            "calculateBenefit",
            {
                "policy_id": claim.policy_id,
                "claim_type": claim.claim_type,
                "amount": str(claim.amount),
            },
        ),
    ]


class ScriptedLLM:
    def next_tool_call(self, conversation: Sequence[Turn], tools: Sequence[Tool]) -> ToolCall:
        claim = Claim.model_validate_json(str(conversation[0]))
        made = sum(isinstance(turn, ToolCall) for turn in conversation)
        return correct_tool_calls(claim)[made]

    def draft_report(
        self, evidence: Evidence, decision: Decision, validation_errors: Sequence[str]
    ) -> ReportDraft:
        return ReportDraft(
            reasoning=[finding.message for finding in decision.findings],
            policy_citations=sorted(decision.required_citations),
        )

    def answer(self, question: str, assessment: Assessment) -> str:
        return f"{assessment.report.recommendation}: {question}"
