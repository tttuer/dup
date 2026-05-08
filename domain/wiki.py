from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class WikiPage(BaseModel):
    id: str
    title: str
    content: str
    parent_id: Optional[str] = None
    author_id: str
    is_personal: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="ignore")

class WikiImage(BaseModel):
    id: str
    file_name: str
    content_type: str
    file_data: bytes
    uploaded_at: datetime

    model_config = ConfigDict(extra="ignore")
