from dataclasses import dataclass
from typing import Optional

from domain.file import Company


@dataclass
class Group:
    name: str
    id: Optional[str] = None
    company: Optional[Company] = None
