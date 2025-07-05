from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from common.auth import Role


class UserResponse(BaseModel):
    id: str
    name: Optional[str] = None
    user_id: str
    created_at: datetime
    updated_at: datetime
    roles: list[Role]
    
    @classmethod
    def from_document(cls, doc) -> "UserResponse":
        return cls(
            id=doc.id,
            name=doc.name,
            user_id=doc.user_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            roles=doc.roles
        )