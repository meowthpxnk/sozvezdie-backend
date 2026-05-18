from fastapi import Depends
from typing import Annotated
from fastapi.security import HTTPBearer
from app.api.auth_routing import AuthService
from fastapi import HTTPException


bearer_dependency = Depends(HTTPBearer(auto_error=False))

TokenDataSchemaDepends = Annotated[str, bearer_dependency]

from app.api.auth_routing import AuthAPI
from app.schemas.auth import TokenDataSchema
from app.core import auth_api


def gavno():
    return auth_api


AuthAPIDepends = Annotated[
    AuthAPI,
    Depends(gavno),
]


def validate_bearer_token(
    bearer_token: TokenDataSchemaDepends, auth_service: AuthAPIDepends
) -> TokenDataSchema:
    try:
        return auth_service.decode_access_token(bearer_token.credentials)
    except Exception as error:
        raise HTTPException(status_code=401, detail="Invalid token") from error


BearerAuthDepends = Annotated[
    TokenDataSchema,
    Depends(validate_bearer_token),
]

# def bearer_scheme_dep_factory(auto_error: bool = False) -> Depends:
#     return Depends(HTTPBearer(auto_error=auto_error))
