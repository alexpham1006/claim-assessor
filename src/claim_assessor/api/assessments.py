from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from claim_assessor.api.schemas import AnswerResponse, AssessmentResponse, QuestionRequest
from claim_assessor.assessment.models import Claim
from claim_assessor.assessment.service import AssessmentService

router = APIRouter(tags=["assessments"])


def get_assessment_service(request: Request) -> AssessmentService:
    return cast(AssessmentService, request.app.state.assessment_service)


@router.post("/assessments", status_code=201)
def create_assessment(
    claim: Claim,
    service: Annotated[AssessmentService, Depends(get_assessment_service)],
) -> AssessmentResponse:
    return AssessmentResponse.from_domain(service.create_assessment(claim))


@router.get("/assessments/{assessment_id}")
def get_assessment(
    assessment_id: str,
    service: Annotated[AssessmentService, Depends(get_assessment_service)],
) -> AssessmentResponse:
    return AssessmentResponse.from_domain(service.get_assessment(assessment_id))


@router.post("/assessments/{assessment_id}/questions")
def ask_question(
    assessment_id: str,
    body: QuestionRequest,
    service: Annotated[AssessmentService, Depends(get_assessment_service)],
) -> AnswerResponse:
    return AnswerResponse(answer=service.answer_question(assessment_id, body.question))
