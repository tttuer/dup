from pydantic import BaseModel, ConfigDict
from datetime import datetime


class AttachedFile(BaseModel):
    id: str
    request_id: str
    file_name: str
    file_path: str
    file_size: int
    file_type: str
    is_reference: bool = False        # 참조문서 여부
    uploaded_at: datetime
    uploaded_by: str
    
    model_config = ConfigDict(extra="ignore")