from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field


class AttachedFile(Document):
    id: str
    request_id: Optional[str] = Field(default=None)
    payment_task_id: Optional[str] = Field(default=None)
    file_name: str
    gridfs_file_id: str  # GridFS ObjectId as string
    file_size: int
    file_type: str
    is_reference: bool = Field(default=False)        # 참조문서 여부
    attachment_type: str = Field(default="REQUEST") # REQUEST | PAYMENT_REQUEST | PAYMENT_EVIDENCE
    uploaded_at: datetime
    uploaded_by: str

    class Settings:
        name = "attached_files"
