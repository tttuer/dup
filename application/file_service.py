import zlib
from datetime import datetime
from typing import Optional, List

from beanie.operators import And, RegEx, Or, In
from dependency_injector.wiring import inject
from fastapi import UploadFile, HTTPException
from ulid import ULID

from common.auth import Role
from domain.file import File, Company, SearchOption, Type
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
        type: Type,
        lock: bool,
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
                type=type,
                lock=lock,
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
        is_locked: bool,
        role: Role,
        search: Optional[str] = None,
        search_option: Optional[str] = None,
        company: Optional[Company] = Company.BAEKSUNG,
        type: Optional[Type] = Type.VOUCHER,
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

        if is_locked:
            filters.append(FileDocument.lock == True)
        filters.append(FileDocument.company == company)
        filters.append(FileDocument.type == type)

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

        if role == Role.USER:
            filters.append(FileDocument.lock == False)

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

    async def delete_many(self, ids: List[str]):
        await self.file_repo.delete_many(In(FileDocument.id, ids))

    async def update(
        self,
        id: str,
        withdrawn_at: str,
        name: str,
        price: int,
        file_data: UploadFile,
        lock: bool,
    ):
        now = datetime.now()

        file: File = File(
            id=id,
            withdrawn_at=withdrawn_at,
            name=name,
            price=price,
            file_data=await self.compress_pdf(file_data) if file_data else None,
            file_name=file_data.filename if file_data else None,
            updated_at=now,
            lock=lock,
        )

        update_file = await self.file_repo.update(file)

        return update_file
