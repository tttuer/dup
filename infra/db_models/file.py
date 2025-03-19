from datetime import datetime

from beanie import Document


class File(Document):
    id: str
    withdrawn_at: datetime
    name: str
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "files"
        indexes = ["id", "withdrawn_at", "created_at"]
