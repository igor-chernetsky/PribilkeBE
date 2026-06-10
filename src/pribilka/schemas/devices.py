from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    user_id: str
    token: str = Field(..., min_length=10, max_length=512)
    platform: str = Field(default="unknown", max_length=32)
    push_enabled: bool = True


class DeviceRegisterResponse(BaseModel):
    registered: bool
    token: str
