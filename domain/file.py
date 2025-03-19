from dataclasses import dataclass
from datetime import datetime


@dataclass
class File:
    id: str
    withdrawn_at: datetime
    name: str
    created_at: datetime
    updated_at: datetime
