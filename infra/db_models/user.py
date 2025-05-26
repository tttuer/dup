from datetime import datetime

from beanie import Document

from common.auth import Role


class User(Document):
    id: str
    user_id: str
    password: str
    created_at: datetime
    updated_at: datetime
    roles: list[Role]

    class Settings:
        name = "users"
