from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from claim_assessor.assessment.models import (
    BenefitCalculation,
    ClauseType,
    Document,
    MedicalNecessity,
    Policy,
)
from claim_assessor.infrastructure.reference_data import ReferenceData

ToolOutput = Document | Policy | MedicalNecessity | BenefitCalculation


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VerifyDocumentArgs(ToolArgs):
    document_id: str


class LookupPolicyArgs(ToolArgs):
    policy_id: str


class CheckMedicalNecessityArgs(ToolArgs):
    diagnosis_code: str
    procedure_codes: list[str]


class CalculateBenefitArgs(ToolArgs):
    policy_id: str
    claim_type: str
    amount: Decimal = Field(gt=0)


def verify_document(reference_data: ReferenceData, args: VerifyDocumentArgs) -> Document:
    return reference_data.get_document(args.document_id)


def lookup_policy(reference_data: ReferenceData, args: LookupPolicyArgs) -> Policy:
    return reference_data.get_policy(args.policy_id)


def check_medical_necessity(
    reference_data: ReferenceData, args: CheckMedicalNecessityArgs
) -> MedicalNecessity:
    rule = reference_data.find_medical_rule(args.diagnosis_code)
    if rule is None or not set(args.procedure_codes) <= set(rule.procedure_codes):
        return reference_data.medical_fallback
    return MedicalNecessity(status=rule.result, reason=rule.reason)


def calculate_benefit(
    reference_data: ReferenceData, args: CalculateBenefitArgs
) -> BenefitCalculation:
    policy = reference_data.get_policy(args.policy_id)
    benefit = policy.benefits.get(args.claim_type)
    if benefit is None:
        return _not_payable(args.amount, remaining=Decimal(0), clause_ids=[])
    remaining = benefit.remaining_limit_before_claim
    if not benefit.covered:
        return _not_payable(args.amount, remaining, policy.clause_ids(ClauseType.EXCLUSION))

    covered = min(args.amount, benefit.per_claim_limit, remaining)
    coinsurance = (covered * benefit.coinsurance_rate).quantize(Decimal("0.01"))
    insurer_pays = covered - coinsurance
    return BenefitCalculation(
        submitted_amount=args.amount,
        covered_amount=covered,
        coinsurance_amount=coinsurance,
        member_responsibility=args.amount - insurer_pays,
        remaining_limit_before=remaining,
        remaining_limit_after_claim=remaining - insurer_pays,
        clause_ids=policy.clause_ids(
            ClauseType.COVERAGE, ClauseType.BENEFIT_LIMIT, ClauseType.COINSURANCE
        ),
    )


def _not_payable(amount: Decimal, remaining: Decimal, clause_ids: list[str]) -> BenefitCalculation:
    return BenefitCalculation(
        submitted_amount=amount,
        covered_amount=Decimal(0),
        coinsurance_amount=Decimal(0),
        member_responsibility=amount,
        remaining_limit_before=remaining,
        remaining_limit_after_claim=remaining,
        clause_ids=clause_ids,
    )


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    args_model: type[ToolArgs]
    handler: Callable[[ReferenceData, Any], ToolOutput]


TOOLS = {
    tool.name: tool
    for tool in (
        Tool(
            "verifyDocument",
            "Verify one submitted document: type match, completeness, and extracted fields.",
            VerifyDocumentArgs,
            verify_document,
        ),
        Tool(
            "lookupPolicy",
            "Return policy terms: status, coverage period, member, limits, exclusions, clauses.",
            LookupPolicyArgs,
            lookup_policy,
        ),
        Tool(
            "checkMedicalNecessity",
            "Check whether the procedures are medically necessary for the diagnosis code.",
            CheckMedicalNecessityArgs,
            check_medical_necessity,
        ),
        Tool(
            "calculateBenefit",
            "Calculate covered amount, copay, member responsibility, and remaining annual limit.",
            CalculateBenefitArgs,
            calculate_benefit,
        ),
    )
}
