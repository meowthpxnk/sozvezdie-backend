from fastapi import APIRouter, Query

from app.api.dependencies import DatabaseDepends
from app.schemas.api.responses import SellerCardResponse
from app.services.seller_card import SellerCardService

router = APIRouter(prefix="/authors", tags=["Authors"])

POPULAR_AUTHORS_LIMIT = 12


@router.get("")
async def get_authors(
    session: DatabaseDepends,
    popular: bool = Query(default=False),
) -> list[SellerCardResponse]:
    service = SellerCardService(session)
    if popular:
        return await service.get_latest_for_landing(limit=POPULAR_AUTHORS_LIMIT)
    return await service.get_all()
