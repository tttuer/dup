from fastapi import HTTPException

from domain.file import File as FileVo
from domain.repository.file_repo import IFileRepository
from infra.db_models.file import File


class FileRepository(IFileRepository):
    async def save_all(self, files: list[FileVo]):
        new_files = [
            File(
                _id=file.id,
                withdrawn_at=file.withdrawn_at,
                name=file.name,
                file_data=file.file_data,
                created_at=file.created_at,
                updated_at=file.updated_at,
            )
            for file in files
        ]

        await File.insert_many(new_files)

    async def find_by_id(self, id: str) -> File:
        file = await File.get(id)

        if not file:
            raise HTTPException(
                status_code=404,
                detail="File not found",
            )

        return file
