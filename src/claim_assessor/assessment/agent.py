from dataclasses import dataclass, field

from pydantic import ValidationError

from claim_assessor.assessment.llm import LLMClient, ToolCall, ToolResult, Turn
from claim_assessor.assessment.models import (
    AssessmentReport,
    BenefitCalculation,
    Claim,
    Decision,
    Document,
    Evidence,
    MedicalNecessity,
    Policy,
    ToolCallRecord,
)
from claim_assessor.assessment.report import build_report, validate_draft
from claim_assessor.assessment.rules import decide
from claim_assessor.assessment.tools import (
    TOOLS,
    CalculateBenefitArgs,
    CheckMedicalNecessityArgs,
    LookupPolicyArgs,
    ToolArgs,
    ToolOutput,
    VerifyDocumentArgs,
)
from claim_assessor.errors import AssessmentFailedError, ToolCallRejectedError
from claim_assessor.infrastructure.reference_data import ReferenceData

MAX_TOOL_CALLS = 20
MAX_REPORT_ATTEMPTS = 2


@dataclass(frozen=True, slots=True)
class AgentResult:
    report: AssessmentReport
    tool_calls: list[ToolCallRecord]


class AssessmentAgent:
    def __init__(self, reference_data: ReferenceData, llm_client: LLMClient) -> None:
        self._reference_data = reference_data
        self._llm_client = llm_client

    def run(self, claim: Claim) -> AgentResult:
        evidence, tool_calls = self._collect_evidence(claim)
        decision = decide(evidence)
        report = self._draft_report(evidence, decision)
        return AgentResult(report, tool_calls)

    def _collect_evidence(self, claim: Claim) -> tuple[Evidence, list[ToolCallRecord]]:
        collector = EvidenceCollector(claim=claim)
        records: list[ToolCallRecord] = []
        conversation: list[Turn] = [claim.model_dump_json()]
        while collector.next_required_tool() is not None:
            if len(records) >= MAX_TOOL_CALLS:
                raise AssessmentFailedError(f"Exceeded {MAX_TOOL_CALLS} tool calls")
            tool_call = self._llm_client.next_tool_call(conversation, list(TOOLS.values()))
            record = self._execute(collector, tool_call, sequence=len(records) + 1)
            records.append(record)
            conversation += [tool_call, ToolResult(name=tool_call.name, payload=record.payload)]
        return collector.to_evidence(), records

    def _execute(
        self, collector: "EvidenceCollector", tool_call: ToolCall, sequence: int
    ) -> ToolCallRecord:
        record = ToolCallRecord(
            sequence=sequence, tool=tool_call.name, arguments=tool_call.arguments
        )
        tool = TOOLS.get(tool_call.name)
        if tool is None:
            return record.model_copy(update={"error": f"Rejected: unknown tool {tool_call.name}"})
        try:
            args = tool.args_model.model_validate(tool_call.arguments)
            collector.check_call(tool_call.name, args)
        except (ValidationError, ToolCallRejectedError) as error:
            return record.model_copy(update={"error": f"Rejected: {error}"})
        output = tool.handler(self._reference_data, args)
        collector.add(output)
        return record.model_copy(update={"output": output.model_dump(mode="json")})

    def _draft_report(self, evidence: Evidence, decision: Decision) -> AssessmentReport:
        validation_errors: list[str] = []
        for _ in range(MAX_REPORT_ATTEMPTS):
            draft = self._llm_client.draft_report(evidence, decision, validation_errors)
            validation_errors = validate_draft(evidence, decision, draft)
            if not validation_errors:
                return build_report(evidence, decision, draft)
        raise AssessmentFailedError(f"Report failed validation: {validation_errors}")


@dataclass
class EvidenceCollector:
    claim: Claim
    documents: list[Document] = field(default_factory=list)
    policy: Policy | None = None
    medical: MedicalNecessity | None = None
    benefit: BenefitCalculation | None = None

    def next_required_tool(self) -> str | None:
        if self.pending_documents():
            return "verifyDocument"
        if self.policy is None:
            return "lookupPolicy"
        if self.medical is None:
            return "checkMedicalNecessity"
        if self.benefit is None:
            return "calculateBenefit"
        return None

    def pending_documents(self) -> list[str]:
        verified = {document.document_id for document in self.documents}
        submitted = [document.document_id for document in self.claim.submitted_documents]
        return [document_id for document_id in submitted if document_id not in verified]

    def check_call(self, tool_name: str, args: ToolArgs) -> None:
        expected_tool = self.next_required_tool()
        if tool_name != expected_tool:
            raise ToolCallRejectedError(f"Call {expected_tool} next, not {tool_name}")
        if isinstance(args, VerifyDocumentArgs):
            if args.document_id not in self.pending_documents():
                raise ToolCallRejectedError(
                    f"document_id must be one of {self.pending_documents()}"
                )
            return
        expected_args = self._expected_args(tool_name)
        if args != expected_args:
            raise ToolCallRejectedError(f"Use the claim values: {expected_args.model_dump_json()}")

    def _expected_args(self, tool_name: str) -> ToolArgs:
        claim = self.claim
        match tool_name:
            case "lookupPolicy":
                return LookupPolicyArgs(policy_id=claim.policy_id)
            case "checkMedicalNecessity":
                return CheckMedicalNecessityArgs(
                    diagnosis_code=claim.diagnosis_code, procedure_codes=claim.procedure_codes
                )
            case "calculateBenefit":
                return CalculateBenefitArgs(
                    policy_id=claim.policy_id, claim_type=claim.claim_type, amount=claim.amount
                )
            case _:
                raise ToolCallRejectedError(f"Unknown tool {tool_name}")

    def add(self, output: ToolOutput) -> None:
        match output:
            case Document():
                self.documents.append(output)
            case Policy():
                self.policy = output
            case MedicalNecessity():
                self.medical = output
            case BenefitCalculation():
                self.benefit = output

    def to_evidence(self) -> Evidence:
        if self.policy is None or self.medical is None or self.benefit is None:
            raise AssessmentFailedError("Evidence is incomplete")
        return Evidence(
            claim=self.claim,
            documents=self.documents,
            policy=self.policy,
            medical=self.medical,
            benefit=self.benefit,
        )
