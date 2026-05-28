from pydantic import BaseModel, Field


class VkAuthoriseRequest(BaseModel):
    vk_access_token: str = Field(..., min_length=1)
