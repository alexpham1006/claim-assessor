import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from claim_assessor.errors import AssessmentFailedError, ClaimAssessorError, LLMError, NotFoundError

logger = logging.getLogger(__name__)


async def _handle_domain_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(error)})
    if isinstance(error, LLMError | AssessmentFailedError):
        logger.warning("upstream failure", exc_info=error, extra={"path": request.url.path})
        return JSONResponse(
            status_code=502, content={"detail": "Assessment could not be completed"}
        )
    logger.error("unhandled domain error", exc_info=error, extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Internal error"})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ClaimAssessorError, _handle_domain_error)
