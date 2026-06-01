from fastapi import APIRouter, Query

from app.api.dependencies import DatabaseDepends
from app.schemas.api.responses import FaqItemResponse
from app.services.faq_item import FaqItemService

router = APIRouter(prefix="/faq", tags=["FAQ"])


@router.get("")
async def list_faq_items(
    session: DatabaseDepends,
    search: str | None = Query(default=None),
) -> list[FaqItemResponse]:
    return await FaqItemService(session).list_items(search=search)
