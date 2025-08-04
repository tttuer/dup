from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from common.auth import Role, ApprovalStatus


@dataclass
class User:
    id: str
    user_id: str
    password: str
    created_at: datetime
    updated_at: datetime
    roles: list[Role]
    name: Optional[str] = None
    approval_status: Optional[ApprovalStatus] = None
