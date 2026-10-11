from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.v1.api import api_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.services.bootstrap import ensure_initial_admin

    await ensure_initial_admin()
    yield


app = FastAPI(
    title="MatchLambda API",
    version="1.3.0",
    docs_url="/docs" if settings.SHOW_DOCS else None,
    redoc_url="/redoc" if settings.SHOW_DOCS else None,
    lifespan=lifespan,
)

def _cors_origins() -> list[str]:
    origins = []
    candidates = [settings.APP_ORIGIN]
    # Localhost origins are only added when a deployment explicitly opts in, so
    # a host-local browser is never a trusted credentialed origin by default.
    if settings.ALLOW_LOCAL_ORIGINS:
        candidates.extend(["http://localhost:3000", "http://127.0.0.1:3000"])
    for origin in candidates:
        if origin and origin != "*" and origin not in origins:
            origins.append(origin)
    return origins


# Credentials cannot be combined with a wildcard origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers enforcing unified JSON error envelope
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Mount /v1 API routes
app.include_router(api_router, prefix="/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": "1.3.0"}
