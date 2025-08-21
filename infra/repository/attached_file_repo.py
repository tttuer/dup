from typing import List, Optional

from domain.repository.attached_file_repo import IAttachedFileRepository
from domain.attached_file import AttachedFile as AttachedFileVo
from infra.db_models.attached_file import AttachedFile
from infra.repository.base_repo import BaseRepository


class AttachedFileRepository(BaseRepository[AttachedFile], IAttachedFileRepository):
    def __init__(self):
        super().__init__(AttachedFile)

    async def save(self, file: AttachedFileVo) -> None:
        new_file = AttachedFile(
            id=file.id,
            request_id=file.request_id,
            file_name=file.file_name,
            file_path=file.file_path,
            file_size=file.file_size,
            file_type=file.file_type,
            is_reference=file.is_reference,
            uploaded_at=file.uploaded_at,
            uploaded_by=file.uploaded_by,
        )
        await new_file.insert()

    async def find_by_id(self, file_id: str) -> Optional[AttachedFile]:
        return await AttachedFile.get(file_id)
    
    async def find_by_request_id(self, request_id: str) -> List[AttachedFile]:
        files = await AttachedFile.find(AttachedFile.request_id == request_id).sort(-AttachedFile.uploaded_at).to_list()
        return files or []
    
    async def find_by_uploader(self, uploaded_by: str) -> List[AttachedFile]:
        files = await AttachedFile.find(AttachedFile.uploaded_by == uploaded_by).sort(-AttachedFile.uploaded_at).to_list()
        return files or []
    
    async def delete(self, file_id: str) -> None:
        await self.delete_by_id(file_id)
    
    async def delete_by_request_id(self, request_id: str) -> None:
        files = await self.find_by_request_id(request_id)
        for file in files:
            await file.delete()