from datetime import datetime

from beanie import Document
from pydantic import ConfigDict, Field
from pymongo import TEXT, IndexModel

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
        indexes = [
            "id",
            "withdrawn_at",
            "created_at",
            "company",
            "price",
            IndexModel(
                [("name", TEXT), ("file_name", TEXT)],
                name="text_index_name_filename",
            ),
            IndexModel([("price", 1)]),  # 숫자 인덱스도 따로 걸어줌
        ]

    model_config = ConfigDict(arbitrary_types_allowed=True)
