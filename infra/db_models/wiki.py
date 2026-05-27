from typing import Optional
from beanie import Document
from pydantic import Field
from datetime import datetime

class WikiPage(Document):
    id: str = Field(alias="_id")
    title: str
    content: str
    parent_id: Optional[str] = None
    author_id: str
    is_personal: bool = False
    attachments: list[dict] = Field(default_factory=list)
    order: int = 0
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "wiki_pages"

class WikiImage(Document):
    id: str = Field(alias="_id")
    file_name: str
    content_type: str
    file_data: bytes
    uploaded_at: datetime

    class Settings:
        name = "wiki_images"
