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
        indexes = [
            {"key": [("id", 1)], "unique": True},  # id에 unique 인덱스
            {"key": [("withdrawn_at", 1)]},
            {"key": [("created_at", 1)]},
        ]
