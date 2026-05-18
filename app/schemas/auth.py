import enum
from pydantic import BaseModel

from app.schemas.database import UserRoleEnum

class User(BaseModel):
    username: str
    role: str

class JWTTokenTypeEnum(enum.Enum):
    ACCESS = "ACCESS"
    REFRESH = "REFRESH"


class TokenPayloadSchema(User):
    session_id: str

class TokenDataSchema(TokenPayloadSchema):
    exp: int
    type: JWTTokenTypeEnum
