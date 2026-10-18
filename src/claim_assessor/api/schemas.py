from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from claim_assessor.assessment.models import Assessment, AssessmentReport, ToolCallRecord
from claim_assessor.assessment.report import render_markdown


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssessmentResponse(ApiModel):
    assessment_id: str
    claim_id: str
    report: AssessmentReport
    markdown: str
    tool_calls: list[ToolCallRecord]
    created_at: datetime

    @classmethod
    def from_domain(cls, assessment: Assessment) -> Self:
        return cls(
            assessment_id=assessment.assessment_id,
            claim_id=assessment.claim.claim_id,
            report=assessment.report,
            markdown=render_markdown(assessment.report),
            tool_calls=assessment.tool_calls,
            created_at=assessment.created_at,
        )


class QuestionRequest(ApiModel):
    question: str = Field(min_length=1, max_length=2000)


class AnswerResponse(ApiModel):
    answer: str
