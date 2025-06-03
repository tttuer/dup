# app/services/sync_status_service.py

from datetime import datetime
from infra.db_models.sync_status import SyncStatus

class SyncService:
    async def set_sync_status(self, syncing: bool):
        now = datetime.now()
        status = await SyncStatus.find_one({})
        if status:
            status.syncing = syncing
            status.updated_at = now
            await status.save()
        else:
            await SyncStatus(syncing=syncing, updated_at=now).insert()
    
    async def get_current_status(self) -> bool:
        status = await SyncStatus.find_one({})
        return status.syncing if status else False

