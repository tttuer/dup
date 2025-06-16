from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field

from common.auth import Role


class User(Document):
    id: str
    name: Optional[str] = Field(default=None)
    user_id: str
    password: str
    created_at: datetime
    updated_at: datetime
    roles: list[Role]

    class Settings:
        name = "users"
