from dataclasses import dataclass
from datetime import datetime

from common.auth import Role


@dataclass
class User:
    id: str
    user_id: str
    password: str
    created_at: datetime
    updated_at: datetime
    roles: list[Role]
