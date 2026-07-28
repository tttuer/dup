from datetime import datetime

from beanie import Document, PydanticObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pydantic import ConfigDict, Field
from typing import Optional


from domain.file import Company, Type


class File(Document):
    id: str = Field(alias="_id")
    group_id: str
    withdrawn_at: str
    name: str
    file_data: bytes
    file_name: str
    created_at: datetime
    updated_at: datetime
    company: Company
    type: Type
    lock: bool

    class Settings:
        name = "files"
        indexes = [
            "withdrawn_at",
            "created_at",
            "company",
            "type",
            "group_id",
            IndexModel([
                ("company", ASCENDING),
                ("type", ASCENDING),
                ("group_id", ASCENDING),
                ("withdrawn_at", DESCENDING),
                ("created_at", DESCENDING),
            ]),
        ]

    model_config = ConfigDict(arbitrary_types_allowed=True)
