from datetime import datetime
from typing import Optional
from common.auth import ApprovalStatus, Role
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    name: Optional[str] = None
    user_id: str
    created_at: datetime
    updated_at: datetime
    roles: list[Role]
    approval_status: Optional[ApprovalStatus] = None
    
    @classmethod
    def from_document(cls, doc) -> "UserResponse":
        return cls(
            id=doc.id,
            name=doc.name,
            user_id=doc.user_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            roles=doc.roles,
            approval_status=doc.approval_status
        )
