from fastapi import APIRouter, HTTPException

from app.api.dependencies import BearerAuthDepends, DatabaseDepends
from app.repositories.specs.user import UserSpec
from app.schemas.api.responses import FandomCreateRequest, FandomResponse
from app.services.fandom import FandomService
from app.services.user import UserService

router = APIRouter()


@router.get("/fandom")
async def get_fandoms(session: DatabaseDepends) -> list[FandomResponse]:
    return await FandomService(session).get_fandoms()


@router.post("/fandom")
async def create_fandom(
    request: FandomCreateRequest,
    session: DatabaseDepends,
    bearer_token: BearerAuthDepends,
) -> FandomResponse:
    user = await UserService(session).get_user(
        bearer_token.username,
        UserSpec(username=bearer_token.username, include_seller_card=True),
    )
    if user is None or user.seller_card is None:
        raise HTTPException(status_code=403, detail="Seller card required")

    try:
        return await FandomService(session).create_fandom(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
