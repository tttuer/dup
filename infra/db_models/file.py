from datetime import datetime

from beanie import Document
from pydantic import ConfigDict, Field

from domain.file import Company


class File(Document):
    id: str = Field(alias="_id")
    withdrawn_at: str
    name: str
    price: int
    file_data: bytes
    file_name: str
    created_at: datetime
    updated_at: datetime
    company: Company

    class Settings:
        name = "files"
        indexes = ["id", "withdrawn_at", "created_at", "company", "price"]

    model_config = ConfigDict(arbitrary_types_allowed=True)
