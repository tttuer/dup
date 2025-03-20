from datetime import datetime

from beanie import Document
from pydantic import ConfigDict, Field


class File(Document):
    id: str = Field(alias="_id")
    withdrawn_at: str
    name: str
    file_data: bytes
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "files"
        indexes = ["id", "withdrawn_at", "created_at"]

    model_config = ConfigDict(arbitrary_types_allowed=True)
