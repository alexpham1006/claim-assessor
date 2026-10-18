import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

from claim_assessor.assessment.agent import AssessmentAgent
from claim_assessor.assessment.llm import LLMClient
from claim_assessor.assessment.models import Assessment, Claim
from claim_assessor.infrastructure.repository import InMemoryAssessmentRepository

logger = logging.getLogger(__name__)


class AssessmentService:
    def __init__(
        self,
        agent: AssessmentAgent,
        repository: InMemoryAssessmentRepository,
        llm_client: LLMClient,
    ) -> None:
        self._agent = agent
        self._repository = repository
        self._llm_client = llm_client

    def create_assessment(self, claim: Claim) -> Assessment:
        started = time.perf_counter()
        result = self._agent.run(claim)
        assessment = Assessment(
            assessment_id=f"ASM-{uuid4().hex}",
            claim=claim,
            report=result.report,
            tool_calls=result.tool_calls,
            created_at=datetime.now(UTC),
        )
        self._repository.save(assessment)
        logger.info(
            "assessment completed",
            extra={
                "assessment_id": assessment.assessment_id,
                "recommendation": assessment.report.recommendation,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            },
        )
        return assessment

    def get_assessment(self, assessment_id: str) -> Assessment:
        return self._repository.get(assessment_id)

    def answer_question(self, assessment_id: str, question: str) -> str:
        return self._llm_client.answer(question, self.get_assessment(assessment_id))
