from pathlib import Path

from pydantic import BaseModel, ValidationError

from claim_assessor.assessment.models import (
    Document,
    MedicalNecessity,
    MedicalRule,
    MedicalStatus,
    Policy,
)
from claim_assessor.errors import DataLoadError, DocumentNotFoundError, PolicyNotFoundError


class _PoliciesFile(BaseModel):
    policies: list[Policy]


class _DocumentsFile(BaseModel):
    documents: list[Document]


class _MedicalFallback(BaseModel):
    result: MedicalStatus
    reason: str


class _MedicalRulesFile(BaseModel):
    version: str
    description: str
    rules: list[MedicalRule]
    fallback: _MedicalFallback


class ReferenceData:
    def __init__(self, data_dir: Path) -> None:
        try:
            policies = _PoliciesFile.model_validate_json((data_dir / "policies.json").read_bytes())
            documents = _DocumentsFile.model_validate_json(
                (data_dir / "documents.json").read_bytes()
            )
            rules = _MedicalRulesFile.model_validate_json(
                (data_dir / "medical_rules.json").read_bytes()
            )
        except (OSError, ValidationError) as error:
            raise DataLoadError(f"Invalid reference data in {data_dir}") from error
        self._policies = {policy.policy_id: policy for policy in policies.policies}
        self._documents = {document.document_id: document for document in documents.documents}
        self._rules = {rule.diagnosis_code: rule for rule in rules.rules}
        self.medical_fallback = MedicalNecessity(
            status=rules.fallback.result, reason=rules.fallback.reason
        )

    def get_policy(self, policy_id: str) -> Policy:
        try:
            return self._policies[policy_id]
        except KeyError:
            raise PolicyNotFoundError(f"Unknown policy: {policy_id}") from None

    def get_document(self, document_id: str) -> Document:
        try:
            return self._documents[document_id]
        except KeyError:
            raise DocumentNotFoundError(f"Unknown document: {document_id}") from None

    def find_medical_rule(self, diagnosis_code: str) -> MedicalRule | None:
        return self._rules.get(diagnosis_code)
