from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from domain.file import Company


@dataclass
class Group:
    id: str
    name: str
    company: Optional[Company] = None
    auth_users: Optional[list[str]] = None
    last_file_changed_at: Optional[datetime] = None
