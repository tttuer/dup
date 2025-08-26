from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import datetime


class ApprovalFavoriteGroup(BaseModel):
    id: str
    user_id: str              # 그룹 소유자 ID
    name: str                 # 그룹 이름
    approver_ids: List[str]   # 결재자 ID 목록
    approver_names: List[str] # 결재자 이름 목록 (캐시용)
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(extra="ignore")