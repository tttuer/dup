from dataclasses import dataclass
from typing import Optional

from domain.file import Company


@dataclass
class Group:
    id: Optional[str] = None
    name: str
    company: Optional[Company] = None
