import zlib
from datetime import datetime, timezone
from typing import Optional, List

from beanie.operators import And, RegEx, Or, In
from dependency_injector.wiring import inject
from fastapi import UploadFile, HTTPException
from ulid import ULID

from application.base_service import BaseService
from common.auth import Role
from domain.file import File, Company, SearchOption, Type
from domain.repository.file_repo import IFileRepository
from domain.repository.user_repo import IUserRepository
from domain.responses.file_response import FileResponse
from infra.db_models.file import File as FileDocument
from utils.pdf import Pdf


class FileService(BaseService[File]):
    @inject
    def __init__(self, file_repo: IFileRepository, user_repo: IUserRepository):
        super().__init__(user_repo)
        self.file_repo = file_repo
        self.ulid = ULID()

    async def save_files(
        self,
        group_id: str,
        withdrawn_at: str,
        name: str,
        company: Company,
        file_datas: list[UploadFile],
        type: Type,
        lock: bool,
    ):
        now = datetime.now(timezone.utc)
        files: list[File] = [
            File(
                id=self.ulid.generate(),
                group_id=group_id,
                withdrawn_at=withdrawn_at,
                name=name,
                file_data=await Pdf.compress(file_data),
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

    async def find_by_id(self, id: str) -> FileResponse:
        file_doc = await self.file_repo.find_by_id(id)

        return FileResponse.from_document(file_doc)

    async def find_many(
        self,
        is_locked: bool,
        roles: list[Role],
        group_id: str,
        search: Optional[str] = None,
        search_option: Optional[str] = None,
        company: Optional[Company] = Company.BAEKSUNG,
        type: Optional[Type] = Type.VOUCHER,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        page: int = 1,
        items_per_page: int = 30,
    ):
        self._validate_date_range(start_at, end_at)
        
        filters = self._build_search_filters(search, search_option)
        filters.extend(self._build_base_filters(is_locked, company, type, group_id))
        filters.extend(self._build_date_filters(start_at, end_at))
        filters.extend(self._build_role_filters(roles))

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
        
        # Document를 FileResponse로 변환
        file_responses = [FileResponse.from_document(file) for file in files]
        
        return total_count, total_page, file_responses
    
    def _validate_date_range(self, start_at: Optional[str], end_at: Optional[str]):
        """Validate date range parameters."""
        if end_at and start_at and end_at < start_at:
            raise HTTPException(
                status_code=400,
                detail="start_at must be less than end_at",
            )
    
    def _build_search_filters(self, search: Optional[str], search_option: Optional[str]) -> list:
        """Build search filters based on search criteria."""
        filters = []
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
        return filters
    
    def _build_base_filters(self, is_locked: bool, company: Company, type: Type, group_id: str) -> list:
        """Build basic filters for company, type, group, and lock status."""
        filters = [
            FileDocument.company == company,
            FileDocument.type == type,
            FileDocument.group_id == group_id,
        ]
        if is_locked:
            filters.append(FileDocument.lock == True)
        return filters
    
    def _build_date_filters(self, start_at: Optional[str], end_at: Optional[str]) -> list:
        """Build date range filters."""
        filters = []
        if start_at:
            filters.append(FileDocument.withdrawn_at >= start_at)
        if end_at:
            filters.append(FileDocument.withdrawn_at <= end_at)
        return filters
    
    def _build_role_filters(self, roles: list[Role]) -> list:
        """Build role-based filters."""
        filters = []
        if Role.USER in roles:
            filters.append(FileDocument.lock == False)
        return filters

    async def delete(self, id: str):
        await self.file_repo.delete(id)

    async def delete_many(self, ids: List[str]):
        await self.file_repo.delete_many(In(FileDocument.id, ids))

    async def update(
        self,
        id: str,
        group_id: str,
        withdrawn_at: str,
        name: str,
        file_data: UploadFile,
        lock: bool,
    ) -> FileResponse:
        now = datetime.now(timezone.utc)

        file: File = File(
            id=id,
            group_id=group_id,
            withdrawn_at=withdrawn_at,
            name=name,
            file_data=await Pdf.compress(file_data) if file_data else None,
            file_name=file_data.filename if file_data else None,
            updated_at=now,
            lock=lock,
        )

        updated_file_doc = await self.file_repo.update(file)

        return FileResponse.from_document(updated_file_doc)
