from typing import List, Optional

from common.db import client

from domain.repository.attached_file_repo import IAttachedFileRepository
from domain.attached_file import AttachedFile as AttachedFileVo
from infra.db_models.attached_file import AttachedFile
from infra.repository.base_repo import BaseRepository


class AttachedFileRepository(BaseRepository[AttachedFile], IAttachedFileRepository):
    def __init__(self):
        super().__init__(AttachedFile)

    async def get_completed_file_ids(self, file_ids: List[str], user_id: str) -> set[str]:
        if not file_ids:
            return set()
        keys = [{"file_id": file_id, "user_id": user_id} for file_id in file_ids]
        records = client.dup.personal_file_checks.find({"_id": {"$in": keys}})
        return {record["_id"]["file_id"] async for record in records}

    async def set_completed(self, file_id: str, user_id: str, completed: bool) -> None:
        # 복합 기본키로 사용자별 중복 기록과 동시 저장 충돌을 방지한다.
        query = {"_id": {"file_id": file_id, "user_id": user_id}}
        checks = client.dup.personal_file_checks
        if completed:
            await checks.update_one(query, {"$set": {"completed": True}}, upsert=True)
        else:
            await checks.delete_one(query)

    async def save(self, file: AttachedFileVo) -> None:
        new_file = AttachedFile(
            id=file.id,
            request_id=file.request_id,
            payment_task_id=file.payment_task_id,
            payment_task_series_id=file.payment_task_series_id,
            file_name=file.file_name,
            gridfs_file_id=file.gridfs_file_id,
            file_size=file.file_size,
            file_type=file.file_type,
            is_reference=file.is_reference,
            attachment_type=file.attachment_type,
            uploaded_at=file.uploaded_at,
            uploaded_by=file.uploaded_by,
        )
        await new_file.insert()

    async def find_by_id(self, file_id: str) -> Optional[AttachedFile]:
        return await AttachedFile.get(file_id)
    
    async def find_by_request_id(self, request_id: str) -> List[AttachedFile]:
        files = await AttachedFile.find(AttachedFile.request_id == request_id).sort(-AttachedFile.uploaded_at).to_list()
        return files or []

    async def find_by_payment_task_id(self, payment_task_id: str) -> List[AttachedFile]:
        files = await AttachedFile.find(
            AttachedFile.payment_task_id == payment_task_id
        ).sort(-AttachedFile.uploaded_at).to_list()
        return files or []

    async def find_by_payment_task_series_id(self, series_id: str) -> List[AttachedFile]:
        files = await AttachedFile.find(
            AttachedFile.payment_task_series_id == series_id
        ).sort(-AttachedFile.uploaded_at).to_list()
        return files or []
    
    async def find_by_uploader(self, uploaded_by: str) -> List[AttachedFile]:
        files = await AttachedFile.find(AttachedFile.uploaded_by == uploaded_by).sort(-AttachedFile.uploaded_at).to_list()
        return files or []
    
    async def delete_by_request_id(self, request_id: str) -> None:
        files = await self.find_by_request_id(request_id)
        for file in files:
            await file.delete()
