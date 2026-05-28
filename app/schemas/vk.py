from pydantic import BaseModel, Field


class VkAuthoriseRequest(BaseModel):
    code: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1, alias="deviceId")
    code_verifier: str = Field(..., min_length=1, alias="codeVerifier")

    model_config = {"populate_by_name": True}
