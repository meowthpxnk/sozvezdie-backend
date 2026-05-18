from pydantic import BaseModel


class CorsConfig(BaseModel):
    allow_origins: list[str]
    allow_headers: list[str]
    allow_methods: list[str]
    allow_credentials: bool
