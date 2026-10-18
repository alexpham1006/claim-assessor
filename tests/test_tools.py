import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from claim_assessor.assessment.models import MedicalStatus
from claim_assessor.assessment.tools import (
    CalculateBenefitArgs,
    CheckMedicalNecessityArgs,
    calculate_benefit,
    check_medical_necessity,
)
from claim_assessor.infrastructure.reference_data import ReferenceData
from tests.fakes import load_claim


def benefit_args(case: str) -> CalculateBenefitArgs:
    claim = load_claim(case)
    return CalculateBenefitArgs(
        policy_id=claim.policy_id, claim_type=claim.claim_type, amount=claim.amount
    )


@pytest.mark.parametrize(
    ("case", "covered", "member_pays"),
    [
        pytest.param("approve", "50000000", "5000000", id="coinsurance-applied"),
        pytest.param("reject", "0", "65000000", id="claim-type-not-covered"),
    ],
)
def test_calculate_benefit_splits_cost_between_insurer_and_member(
    reference_data: ReferenceData, case: str, covered: str, member_pays: str
) -> None:
    result = calculate_benefit(reference_data, benefit_args(case))

    assert result.covered_amount == Decimal(covered)
    assert result.member_responsibility == Decimal(member_pays)


@pytest.mark.parametrize(
    ("limit_field", "limit", "covered", "member_pays"),
    [
        pytest.param("remaining_limit_before_claim", 10000, "10000", "49991000", id="remaining"),
        pytest.param("per_claim_limit", 20000000, "20000000", "32000000", id="per-claim"),
    ],
)
def test_calculate_benefit_is_capped_by_the_lowest_limit(
    tmp_path: Path, limit_field: str, limit: int, covered: str, member_pays: str
) -> None:
    shutil.copytree("data", tmp_path, dirs_exist_ok=True)
    policies = json.loads((tmp_path / "policies.json").read_text())
    policies["policies"][0]["benefits"]["hospitalization"][limit_field] = limit
    (tmp_path / "policies.json").write_text(json.dumps(policies))

    result = calculate_benefit(ReferenceData(tmp_path), benefit_args("approve"))

    assert result.covered_amount == Decimal(covered)
    assert result.member_responsibility == Decimal(member_pays)


def test_check_medical_necessity_uses_fallback_when_procedure_is_unlisted(
    reference_data: ReferenceData,
) -> None:
    args = CheckMedicalNecessityArgs(
        diagnosis_code=load_claim("approve").diagnosis_code, procedure_codes=["UNLISTED-999"]
    )

    result = check_medical_necessity(reference_data, args)

    assert result == reference_data.medical_fallback
    assert result.status is MedicalStatus.NEEDS_REVIEW
