from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field
from pymongo import IndexModel, ASCENDING

from common.auth import Role, ApprovalStatus


class User(Document):
    id: str
    user_id: Indexed(str, unique=True)  # 유니크 인덱스 추가
    password: str
    created_at: datetime
    updated_at: datetime
    roles: list[Role]
    name: Optional[str] = Field(default=None)
    approval_status: Optional[ApprovalStatus] = Field(default=None)  # Optional은 인덱스에서 제외

    class Settings:
        name = "users"
        indexes = [
            # 승인 상태별 인덱스 (Optional 필드는 별도 IndexModel로)
            IndexModel([("approval_status", ASCENDING)]),
            # 이름별 검색 인덱스 (텍스트 검색용)
            IndexModel([("name", ASCENDING)]),
        ]
