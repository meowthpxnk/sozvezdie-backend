
from fastapi import Request, status
from fastapi.responses import JSONResponse
import logging
from app.utils.exceptions import prepare_request_exception

logger = logging.getLogger("app")

async def default_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    error = str(exc)
    logger.error(prepare_request_exception(request.scope, exc))
    return JSONResponse(
        {"error": error}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
