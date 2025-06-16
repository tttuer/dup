from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from common.auth import Role


@dataclass
class User:
    id: str
    name: Optional[str] = None
    user_id: str
    password: str
    created_at: datetime
    updated_at: datetime
    roles: list[Role]
