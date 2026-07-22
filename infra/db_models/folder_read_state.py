from datetime import datetime

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class FolderReadState(Document):
    id: str = Field(alias="_id")
    user_id: str
    group_id: str
    last_seen_at: datetime

    class Settings:
        name = "folder_read_states"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("group_id", ASCENDING)], unique=True),
            IndexModel([("group_id", ASCENDING)]),
        ]
