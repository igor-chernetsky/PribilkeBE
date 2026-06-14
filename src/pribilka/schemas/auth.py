from pydantic import BaseModel, Field


class BootstrapRequest(BaseModel):
    user_id: str = Field(..., min_length=8, max_length=64)


class BootstrapResponse(BaseModel):
    user_id: str
    access_token: str
    issued: bool
