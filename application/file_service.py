import zlib
from datetime import datetime
from typing import Optional

from beanie.operators import And, RegEx, Or
from dependency_injector.wiring import inject
from fastapi import UploadFile, HTTPException
from ulid import ULID

from domain.file import File, Company, SearchOption
from domain.repository.file_repo import IFileRepository
from infra.db_models.file import File as FileDocument


class FileService:
    @inject
    def __init__(self, file_repo: IFileRepository):
        self.file_repo = file_repo
        self.ulid = ULID()

    async def compress_pdf(self, file_data: UploadFile) -> bytes:
        raw_data = await file_data.read()
        compress_data = zlib.compress(raw_data)
        return compress_data

    async def save_files(
        self,
        withdrawn_at: str,
        name: str,
        price: int,
        company: Company,
        file_datas: list[UploadFile],
    ):
        now = datetime.now()
        files: list[File] = [
            File(
                id=self.ulid.generate(),
                withdrawn_at=withdrawn_at,
                name=name,
                price=price,
                file_data=await self.compress_pdf(file_data),
                file_name=file_data.filename,
                created_at=now,
                updated_at=now,
                company=company,
            )
            for file_data in file_datas
        ]

        await self.file_repo.save_all(files)

        return files

    async def find_by_id(self, id: str):
        file = await self.file_repo.find_by_id(id)

        return file

    async def find_many(
        self,
        search: Optional[str] = None,
        search_option: Optional[str] = None,
        company: Optional[Company] = Company.BAEKSUNG,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        page: int = 1,
        items_per_page: int = 30,
    ):
        filters = []

        # ✅ 1. 검색어가 있고, 검색 조건이 명시된 경우
        if search and search_option:
            if search_option == SearchOption.DESCRIPTION_FILENAME:
                filters.append(
                    Or(
                        RegEx(FileDocument.name, f".*{search}.*", options="i"),
                        RegEx(FileDocument.file_name, f".*{search}.*", options="i"),
                    )
                )
            elif search_option == SearchOption.PRICE:
                filters.append(FileDocument.price == int(search))

        filters.append(FileDocument.company == company)

        if start_at and end_at:
            filters.append(FileDocument.withdrawn_at >= start_at)
            filters.append(FileDocument.withdrawn_at <= end_at)
        if start_at:
            filters.append(FileDocument.withdrawn_at >= start_at)

        if end_at and start_at and end_at < start_at:
            raise HTTPException(
                status_code=400,
                detail="start_at must be less than end_at",
            )

        total_count, files = (
            await self.file_repo.find_many(
                And(*filters), page=page, items_per_page=items_per_page
            )
            if filters
            else await self.file_repo.find_many(
                page=page, items_per_page=items_per_page
            )
        )

        total_page = (total_count - 1) // items_per_page + 1

        return total_count, total_page, files

    async def delete(self, id: str):
        await self.file_repo.delete(id)
