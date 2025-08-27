from pydantic import ConfigDict
from datetime import datetime
from typing import Optional
from domain.responses.base_response import BaseResponse


class AttachedFile(BaseResponse):
    id: str
    request_id: str
    file_name: str
    gridfs_file_id: str  # GridFS ObjectId as string
    file_size: int
    file_type: str
    is_reference: bool = False        # 참조문서 여부
    uploaded_at: datetime
    uploaded_by: str
    
    model_config = ConfigDict(extra="ignore")