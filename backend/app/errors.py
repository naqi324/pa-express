from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        retry_guidance: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retry_guidance = retry_guidance
        self.correlation_id = str(uuid4())
        super().__init__(message)


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "status": exc.status_code,
                "code": exc.code,
                "message": exc.message,
                "retry_guidance": exc.retry_guidance,
                "correlation_id": exc.correlation_id,
            }
        },
    )

