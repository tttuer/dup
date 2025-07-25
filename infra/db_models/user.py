from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field

from common.auth import Role


class User(Document):
    id: str
    user_id: str
    password: str
    created_at: datetime
    updated_at: datetime
    roles: list[Role]
    name: Optional[str] = Field(default=None)

    class Settings:
        name = "users"
