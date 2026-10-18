class ClaimAssessorError(Exception):
    pass


class DataLoadError(ClaimAssessorError):
    pass


class NotFoundError(ClaimAssessorError):
    pass


class PolicyNotFoundError(NotFoundError):
    pass


class DocumentNotFoundError(NotFoundError):
    pass


class AssessmentNotFoundError(NotFoundError):
    pass


class ToolCallRejectedError(ClaimAssessorError):
    pass


class LLMError(ClaimAssessorError):
    pass


class AssessmentFailedError(ClaimAssessorError):
    pass
