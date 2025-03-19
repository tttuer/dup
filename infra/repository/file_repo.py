from fastapi import HTTPException

from domain.file import File as FileVo
from domain.repository.file_repo import IFileRepository
from infra.db_models.file import File


class FileRepository(IFileRepository):
    async def save(self, file: FileVo):
        new_file = File(
            id=file.id,
            withdrawn_at=file.withdrawn_at,
            name=file.name,
            file_data=file.file_data,
            created_at=file.created_at,
            updated_at=file.updated_at,
        )

        await new_file.save()

    async def find_by_id(self, id: str) -> File:
        file = await File.find_one(File.id == id)

        if not file:
            raise HTTPException(
                status_code=404,
                detail="File not found",
            )

        return file
