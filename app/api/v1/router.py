"""API v1 router — aggregates all v1 endpoint routers."""

from fastapi import APIRouter

from app.api.v1.bridge import router as bridge_router

router = APIRouter()
router.include_router(bridge_router, tags=["bridge"])
