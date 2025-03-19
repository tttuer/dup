from datetime import datetime

from beanie import Document


class User(Document):
    id: str
    user_id: str
    password: str
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "users"
