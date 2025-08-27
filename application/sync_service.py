# app/services/sync_status_service.py

from datetime import datetime, timezone
from infra.db_models.sync_status import SyncStatus
from redis.asyncio import Redis


class SyncService:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.key = "sync_status"

    async def set_sync_status(self, syncing: bool):
        now = datetime.now(timezone.utc)
        status = SyncStatus(syncing=syncing, updated_at=now)
        await self.redis.set(self.key, status.model_dump_json())

    async def get_current_status(self) -> bool:
        raw_data = await self.redis.get(self.key)
        if raw_data is None:
            return False
        status = SyncStatus.model_validate_json(raw_data)

        return status.syncing

