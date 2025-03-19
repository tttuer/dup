from datetime import datetime

from beanie import Document
from bson import Binary


class File(Document):
    _id: str
    withdrawn_at: str
    name: str
    file_data: Binary
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "files"
        indexes = ["id", "withdrawn_at", "created_at"]
