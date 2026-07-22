from dataclasses import dataclass
from datetime import datetime


@dataclass
class FolderReadState:
    id: str
    user_id: str
    group_id: str
    last_seen_at: datetime
