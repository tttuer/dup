from dataclasses import dataclass
from datetime import datetime

from bson import Binary


@dataclass
class File:
    id: str
    withdrawn_at: str
    name: str
    created_at: datetime
    updated_at: datetime
    file_data: Binary
