from fastapi import APIRouter

from . import docs, favicon

router = APIRouter()
router.include_router(docs.router)
router.include_router(favicon.router)
