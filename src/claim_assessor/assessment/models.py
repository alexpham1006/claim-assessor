from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClauseType(StrEnum):
    COVERAGE = "coverage"
    BENEFIT_LIMIT = "benefit_limit"
    COINSURANCE = "coinsurance"
    REQUIRED_DOCUMENTS = "required_documents"
    EXCLUSION = "exclusion"


class Recommendation(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_MORE_INFO = "REQUEST_MORE_INFO"


class DocumentStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    TYPE_MISMATCH = "type_mismatch"


class MedicalStatus(StrEnum):
    SUPPORTED = "supported"
    NEEDS_REVIEW = "needs_review"


class Claim(DomainModel):
    claim_id: str = Field(min_length=1, max_length=64)
    policy_id: str = Field(min_length=1, max_length=64)
    member_id: str = Field(min_length=1, max_length=64)
    claim_type: str = Field(min_length=1, max_length=32)
    diagnosis: str = Field(min_length=1, max_length=500)
    diagnosis_code: str = Field(min_length=1, max_length=16)
    procedures: list[str] = Field(max_length=50)
    procedure_codes: list[str] = Field(max_length=50)
    treatment_date: date
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    submitted_documents: list["SubmittedDocument"] = Field(max_length=50)

    @model_validator(mode="after")
    def _validate_claim(self) -> Self:
        if len(self.procedures) != len(self.procedure_codes):
            raise ValueError("procedures and procedure_codes must have the same length")
        document_ids = [document.document_id for document in self.submitted_documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("submitted_documents must contain unique document IDs")
        return self


class SubmittedDocument(DomainModel):
    document_id: str


class Document(DomainModel):
    document_id: str
    document_type: str
    status: DocumentStatus
    issues: list[str] = Field(default_factory=list)
    extracted_data: dict[str, object] = Field(default_factory=dict)


class Clause(DomainModel):
    clause_id: str
    type: ClauseType
    title: str
    text: str


class Exclusion(DomainModel):
    exclusion_id: str
    description: str
    applies_to: list[str]


class Policyholder(DomainModel):
    member_id: str
    name: str


class CoveragePeriod(DomainModel):
    start_date: date
    end_date: date


class ClaimRequirement(DomainModel):
    required_documents: list[str]


class BenefitTerms(DomainModel):
    covered: bool
    annual_limit: Decimal
    remaining_limit_before_claim: Decimal
    per_claim_limit: Decimal
    coinsurance_rate: Decimal


class WaitingPeriod(DomainModel):
    months: int
    satisfied: bool


class Policy(DomainModel):
    policy_id: str
    policyholder: Policyholder
    status: str
    coverage_period: CoveragePeriod
    claim_requirements: dict[str, ClaimRequirement]
    benefits: dict[str, BenefitTerms]
    waiting_period: WaitingPeriod
    exclusions: list[Exclusion]
    clauses: list[Clause]

    def covers_member(self, member_id: str) -> bool:
        return self.policyholder.member_id == member_id

    def covers_date(self, day: date) -> bool:
        return self.coverage_period.start_date <= day <= self.coverage_period.end_date

    def covers_claim_type(self, claim_type: str) -> bool:
        benefit = self.benefits.get(claim_type)
        return benefit is not None and benefit.covered

    def clause_id(self, clause_type: ClauseType) -> str | None:
        return next(
            (clause.clause_id for clause in self.clauses if clause.type is clause_type), None
        )

    def clause_ids(self, *clause_types: ClauseType) -> list[str]:
        return [clause.clause_id for clause in self.clauses if clause.type in clause_types]


class MedicalRule(DomainModel):
    rule_id: str
    diagnosis: str
    diagnosis_code: str
    procedures: list[str]
    procedure_codes: list[str]
    result: MedicalStatus
    reason: str


class MedicalNecessity(DomainModel):
    status: MedicalStatus
    reason: str


class BenefitCalculation(DomainModel):
    submitted_amount: Decimal
    covered_amount: Decimal
    coinsurance_amount: Decimal
    member_responsibility: Decimal
    remaining_limit_before: Decimal
    remaining_limit_after_claim: Decimal
    clause_ids: list[str]


class Evidence(DomainModel):
    claim: Claim
    documents: list[Document]
    policy: Policy
    medical: MedicalNecessity
    benefit: BenefitCalculation

    @property
    def required_documents(self) -> list[str]:
        requirements = self.policy.claim_requirements.get(self.claim.claim_type)
        return requirements.required_documents if requirements else []

    @property
    def missing_documents(self) -> list[str]:
        submitted = {document.document_type for document in self.documents}
        return [kind for kind in self.required_documents if kind not in submitted]


@dataclass(frozen=True, slots=True)
class Finding:
    clause_id: str | None
    message: str


class Decision(DomainModel):
    recommendation: Recommendation
    findings: list[Finding] = Field(min_length=1)

    @property
    def required_citations(self) -> set[str]:
        return {finding.clause_id for finding in self.findings if finding.clause_id is not None}


class ReportDraft(DomainModel):
    reasoning: list[str] = Field(min_length=1, max_length=20)
    policy_citations: list[str] = Field(max_length=20)


class PolicyVerification(DomainModel):
    policy_id: str
    status: str
    member_covered: bool
    within_coverage_period: bool
    claim_type_included: bool


class AssessmentReport(DomainModel):
    document_review: list[Document]
    missing_documents: list[str]
    policy_verification: PolicyVerification
    medical_necessity: MedicalNecessity
    benefit_calculation: BenefitCalculation
    recommendation: Recommendation
    findings: list[Finding]
    reasoning: list[str]
    policy_citations: list[str]


class ToolCallRecord(DomainModel):
    sequence: int
    tool: str
    arguments: dict[str, object]
    output: dict[str, object] | None = None
    error: str | None = None

    @property
    def payload(self) -> dict[str, object]:
        return self.output if self.output is not None else {"error": self.error}


class Assessment(DomainModel):
    assessment_id: str
    claim: Claim
    report: AssessmentReport
    tool_calls: list[ToolCallRecord]
    created_at: datetime
