from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field

class SyncStatus(Document):
    syncing: bool
    updated_at: datetime

    class Settings:
        name = "sync_status"