from typing import Any

from fastapi import HTTPException

from domain.file import File as FileVo
from domain.repository.file_repo import IFileRepository
from infra.db_models.file import File


class FileRepository(IFileRepository):
    async def save_all(self, files: list[FileVo]):
        new_files = [
            File(
                id=file.id,
                withdrawn_at=file.withdrawn_at,
                name=file.name,
                price=file.price,
                file_data=file.file_data,
                file_name=file.file_name,
                created_at=file.created_at,
                updated_at=file.updated_at,
                company=file.company,
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
