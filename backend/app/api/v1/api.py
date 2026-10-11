from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.matches import router as matches_router
from app.api.v1.payments import router as payments_router
from app.api.v1.alpha import router as alpha_router
from app.api.v1.admin import admin_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(matches_router)
api_router.include_router(payments_router)
api_router.include_router(alpha_router)
api_router.include_router(admin_router)
