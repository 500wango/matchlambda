from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.api.v1.api import api_router

app = FastAPI(
    title="MatchLambda API",
    version="1.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS restricted to APP_ORIGIN according to architecture spec
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.APP_ORIGIN,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers enforcing unified JSON error envelope
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Mount /v1 API routes
app.include_router(api_router, prefix="/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": "1.3.0"}
