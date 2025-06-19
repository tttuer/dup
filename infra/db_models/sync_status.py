from pydantic import BaseModel
from datetime import datetime

class SyncStatus(BaseModel):
    syncing: bool
    updated_at: datetime