from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from claim_assessor.api import assessments, health
from claim_assessor.api.errors import register_error_handlers
from claim_assessor.assessment.agent import AssessmentAgent
from claim_assessor.assessment.service import AssessmentService
from claim_assessor.config import Settings, get_settings
from claim_assessor.infrastructure.gemini import GeminiClient
from claim_assessor.infrastructure.reference_data import ReferenceData
from claim_assessor.infrastructure.repository import InMemoryAssessmentRepository


def build_assessment_service(settings: Settings) -> AssessmentService:
    llm_client = GeminiClient(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_attempts=settings.gemini_max_attempts,
    )
    reference_data = ReferenceData(settings.data_dir)
    agent = AssessmentAgent(reference_data, llm_client)
    return AssessmentService(agent, InMemoryAssessmentRepository(), llm_client)


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.assessment_service = build_assessment_service(settings or get_settings())
        yield

    app = FastAPI(title="Claim Assessor", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(assessments.router)
    register_error_handlers(app)
    return app


app = create_app()
