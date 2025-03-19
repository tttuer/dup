from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: str
    user_id: str
    password: str
    created_at: datetime
    updated_at: datetime
