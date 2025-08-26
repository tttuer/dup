from datetime import datetime
from typing import List

from beanie import Document
from pydantic import Field


class ApprovalFavoriteGroup(Document):
    id: str
    user_id: str              # 그룹 소유자 ID
    name: str                 # 그룹 이름
    approver_ids: List[str]   # 결재자 ID 목록
    approver_names: List[str] # 결재자 이름 목록 (캐시용)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "approval_favorite_groups"