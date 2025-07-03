from dataclasses import asdict
from typing import Any

from fastapi import HTTPException

from domain.file import File as FileVo
from domain.repository.file_repo import IFileRepository
from infra.db_models.file import File
from infra.repository.base_repo import BaseRepository


class FileRepository(BaseRepository[File], IFileRepository):
    def __init__(self):
        super().__init__(File)
    async def save_all(self, files: list[FileVo]):
        new_files = [
            File(
                id=file.id,
                group_id=file.group_id,
                withdrawn_at=file.withdrawn_at,
                name=file.name,
                file_data=file.file_data,
                file_name=file.file_name,
                created_at=file.created_at,
                updated_at=file.updated_at,
                company=file.company,
                type=file.type,
                lock=file.lock,
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

        return FileVo(**file.model_dump())

    async def find_many(
        self,
        *filters: Any,
        page: int = 1,
        items_per_page: int = 10,
    ) -> tuple[int, list[FileVo]]:
        offset = (page - 1) * items_per_page

        if filters:
            total_count = await File.find(*filters).sort("withdrawn_at").count()

            files = (
                await File.find(*filters)
                .sort("withdrawn_at")
                .skip(offset)
                .limit(items_per_page)
                .to_list()
            )

            return (
                total_count,
                [FileVo(**file.model_dump()) for file in files],
            )
        total_count = await File.count()

        files = (
            await File.find()
            .sort("withdrawn_at")
            .skip(offset)
            .limit(items_per_page)
            .to_list()
        )

        return (
            total_count,
            [FileVo(**file.model_dump()) for file in files],
        )

    async def delete(self, id: str):
        file = await File.get(id)

        if not file:
            raise HTTPException(
                status_code=404,
            )

        await file.delete()

    async def delete_many(self, *filters):
        await File.find(*filters).delete()

    async def delete_by_group_id(self, group_id: str, session=None):
        await File.find(File.group_id == group_id).delete(session=session)

    async def update(self, update_file: FileVo):
        db_file = await File.get(update_file.id)

        if not db_file:
            raise HTTPException(
                status_code=404,
                detail="File not found",
            )

        update_data = asdict(update_file)
        update_data.pop("id", None)

        for field, value in update_data.items():
            if value is not None:
                setattr(db_file, field, value)

        await db_file.save()
        return db_file
