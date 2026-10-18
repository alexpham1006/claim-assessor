import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from claim_assessor.api.assessments import get_assessment_service
from claim_assessor.assessment.agent import AssessmentAgent
from claim_assessor.assessment.llm import LLMClient, ToolCall, Turn
from claim_assessor.assessment.service import AssessmentService
from claim_assessor.assessment.tools import Tool
from claim_assessor.config import Settings
from claim_assessor.errors import LLMError
from claim_assessor.infrastructure.reference_data import ReferenceData
from claim_assessor.infrastructure.repository import InMemoryAssessmentRepository
from claim_assessor.main import create_app
from tests.fakes import ScriptedLLM


class UnavailableLLM(ScriptedLLM):
    def next_tool_call(self, conversation: Sequence[Turn], tools: Sequence[Tool]) -> ToolCall:
        raise LLMError("Gemini request failed with status 503")


def make_client(reference_data: ReferenceData, llm_client: LLMClient) -> TestClient:
    service = AssessmentService(
        AssessmentAgent(reference_data, llm_client),
        InMemoryAssessmentRepository(),
        llm_client,
    )
    settings = Settings(
        _env_file=None,
        gemini_api_key=SecretStr("unused"),
        gemini_model="test-model",
        data_dir=Path("data"),
    )
    app = create_app(settings)
    app.dependency_overrides[get_assessment_service] = lambda: service
    return TestClient(app)


@pytest.fixture
def client(reference_data: ReferenceData) -> Iterator[TestClient]:
    with make_client(reference_data, ScriptedLLM()) as test_client:
        yield test_client


def load_case(name: str) -> dict[str, object]:
    return json.loads(Path("test_cases", f"{name}.json").read_text())


@pytest.mark.parametrize(
    ("case", "recommendation"),
    [
        ("approve", "APPROVE"),
        ("reject", "REJECT"),
        ("request_more_info", "REQUEST_MORE_INFO"),
    ],
)
def test_assessment_recommendation_per_case(
    client: TestClient, case: str, recommendation: str
) -> None:
    response = client.post("/assessments", json=load_case(case))

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["recommendation"] == recommendation
    assert all(call["error"] is None for call in body["tool_calls"])


def test_assessment_can_be_read_and_questioned(client: TestClient) -> None:
    assessment_id = client.post("/assessments", json=load_case("approve")).json()["assessment_id"]

    stored = client.get(f"/assessments/{assessment_id}")
    answer = client.post(f"/assessments/{assessment_id}/questions", json={"question": "Why?"})

    assert stored.json()["assessment_id"] == assessment_id
    assert answer.json()["answer"].startswith("APPROVE")


def test_llm_failure_returns_502_without_internal_details(reference_data: ReferenceData) -> None:
    with make_client(reference_data, UnavailableLLM()) as client:
        response = client.post("/assessments", json=load_case("approve"))

    assert response.status_code == 502
    assert response.json() == {"detail": "Assessment could not be completed"}


def test_unknown_assessment_returns_404(client: TestClient) -> None:
    assert client.get("/assessments/ASM-missing").status_code == 404


def test_claim_with_unknown_document_returns_404(client: TestClient) -> None:
    claim = load_case("approve") | {"submitted_documents": [{"document_id": "NOT-A-DOC"}]}

    assert client.post("/assessments", json=claim).status_code == 404


@pytest.mark.parametrize(
    "invalid_fields",
    [
        pytest.param({"amount": -1}, id="negative-amount"),
        pytest.param({"procedure_codes": []}, id="procedures-without-codes"),
        pytest.param(
            {"submitted_documents": [{"document_id": "DOC-001"}, {"document_id": "DOC-001"}]},
            id="duplicate-documents",
        ),
    ],
)
def test_invalid_claim_returns_422(client: TestClient, invalid_fields: dict[str, object]) -> None:
    claim = load_case("approve") | invalid_fields

    assert client.post("/assessments", json=claim).status_code == 422
