from fastapi import APIRouter

from . import user, utils, auth, product, advert_banner, author, authors, cart, favourite, order, category, fandom, moderation, super_admin
from fastapi import Depends
from app.api.dependencies import BearerAuthDepends, validate_bearer_token

# from .auth import router as auth_router

internal_router = APIRouter(dependencies=[Depends(validate_bearer_token)])

internal_router.include_router(user.router)
# internal_router.include_router(product.router)
auth_router = APIRouter()

auth_router.include_router(author.router)
auth_router.include_router(authors.router)
auth_router.include_router(advert_banner.router)
auth_router.include_router(product.router)
auth_router.include_router(category.router)
auth_router.include_router(fandom.router)
auth_router.include_router(auth.router)
auth_router.include_router(utils.router)
auth_router.include_router(cart.router)
auth_router.include_router(favourite.router)
auth_router.include_router(order.router)
auth_router.include_router(moderation.router)
auth_router.include_router(super_admin.router)
router = APIRouter()

router.include_router(internal_router)
router.include_router(auth_router)
