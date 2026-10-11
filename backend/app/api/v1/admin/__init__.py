from fastapi import APIRouter
from app.api.v1.admin.etl import router as etl_router
from app.api.v1.admin.model import router as model_router
from app.api.v1.admin.billing import router as billing_router
from app.api.v1.admin.settings import router as settings_router

admin_router = APIRouter(prefix="/admin", tags=["Admin"])
admin_router.include_router(etl_router, prefix="/etl", tags=["Admin - ETL"])
admin_router.include_router(model_router, prefix="/model", tags=["Admin - Model"])
admin_router.include_router(billing_router, prefix="/billing", tags=["Admin - Billing & Users"])
admin_router.include_router(settings_router, prefix="/settings", tags=["Admin - Settings"])
