from dataclasses import dataclass
from typing import Optional

from domain.file import Company


@dataclass
class Group:
    id: str
    name: str
    company: Optional[Company] = None
    auth_users: list[str] = None
