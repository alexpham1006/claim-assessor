from claim_assessor.assessment.models import Assessment
from claim_assessor.errors import AssessmentNotFoundError


# Process-local: assessments are lost on restart and not shared across workers.
class InMemoryAssessmentRepository:
    def __init__(self) -> None:
        self._assessments: dict[str, Assessment] = {}

    def save(self, assessment: Assessment) -> None:
        self._assessments[assessment.assessment_id] = assessment

    def get(self, assessment_id: str) -> Assessment:
        try:
            return self._assessments[assessment_id]
        except KeyError:
            raise AssessmentNotFoundError(f"Unknown assessment: {assessment_id}") from None
