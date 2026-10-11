import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    def __init__(self, status_code: int, code: str, message: str, headers: dict = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}
        super().__init__(message)


def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
        headers=exc.headers,
    )


def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # AppException carries PASS_REQUIRED itself. A bare HTTP 403 is FORBIDDEN.
    code_map = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHENTICATED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_409_CONFLICT: "CONFLICT",
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "PAYLOAD_TOO_LARGE",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
        status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    }
    # Fixed, non-revealing copy per status so an upstream handler's `detail`
    # (which can leak internal state codes or paths) is never echoed verbatim.
    safe_messages = {
        status.HTTP_400_BAD_REQUEST: "The request could not be processed.",
        status.HTTP_401_UNAUTHORIZED: "Authentication is required.",
        status.HTTP_403_FORBIDDEN: "You do not have permission to perform this action.",
        status.HTTP_404_NOT_FOUND: "The requested resource was not found.",
        status.HTTP_409_CONFLICT: "The request conflicts with the current state.",
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "The request payload is too large.",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "The request could not be validated.",
        status.HTTP_429_TOO_MANY_REQUESTS: "Too many requests. Please try again later.",
        status.HTTP_503_SERVICE_UNAVAILABLE: "The service is temporarily unavailable.",
    }
    code = code_map.get(exc.status_code, "ERROR")
    message = safe_messages.get(exc.status_code, "The request could not be completed.")
    if exc.status_code >= 500:
        message = "The request could not be completed."
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}},
        headers=getattr(exc, "headers", None) or {},
    )


def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("matchlambda").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "INTERNAL", "message": "The request could not be completed."}},
    )


def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Flatten validation errors into a clean, safe message
    error_messages = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        error_messages.append(f"{loc}: {msg}" if loc else msg)
    message = "; ".join(error_messages) if error_messages else "Request validation failed."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "VALIDATION_ERROR", "message": message}},
    )
