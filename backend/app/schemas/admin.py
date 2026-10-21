from pydantic import BaseModel, Field


class UserStatusUpdate(BaseModel):
    status: int = Field(ge=0, le=1, description="1-启用, 0-停用")
