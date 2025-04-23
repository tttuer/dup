from datetime import datetime

from beanie import Document
from pydantic import ConfigDict, Field
from pymongo import IndexModel

from domain.file import Company, Type


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
    type: Type
    lock: bool

    class Settings:
        name = "files"
        indexes = [
            "withdrawn_at",
            "created_at",
            "company",
            "price",
            "type",
            IndexModel([("price", 1)]),  # 숫자 인덱스도 따로 걸어줌
        ]

    model_config = ConfigDict(arbitrary_types_allowed=True)
