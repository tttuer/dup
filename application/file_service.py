import zlib
from datetime import datetime, timezone
from typing import Optional, List

from beanie.operators import And, RegEx, Or, In
from dependency_injector.wiring import inject
from fastapi import UploadFile
from ulid import ULID

from application.base_service import BaseService
from common.auth import Role
from domain.file import File, Company, SearchOption, Type
from domain.repository.file_repo import IFileRepository
from domain.repository.group_repo import IGroupRepository
from domain.repository.user_repo import IUserRepository
from domain.responses.file_response import FileResponse, FileListResponse
from infra.db_models.file import File as FileDocument
from utils.pdf import Pdf
from common.exceptions import ValidationError
from utils.time import get_utc_now_naive


class FileService(BaseService[File]):
    @inject
    def __init__(
        self,
        file_repo: IFileRepository,
        group_repo: IGroupRepository,
        user_repo: IUserRepository,
    ):
        super().__init__(user_repo)
        self.file_repo = file_repo
        self.group_repo = group_repo
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
        now = get_utc_now_naive()
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
        await self._record_extra_file_change(type, now, group_id)

        return files

    async def find_by_id(self, id: str) -> FileResponse:
        file_doc = await self.file_repo.find_by_id(id)

        return FileResponse.from_document(file_doc)

    async def find_many(
        self,
        is_locked: bool,
        roles: list[Role],
        group_id: Optional[str],
        search: Optional[str] = None,
        search_option: Optional[str] = None,
        company: Optional[Company] = Company.BAEKSUNG,
        type: Optional[Type] = Type.VOUCHER,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        sort_by: str = "created_at",
        order: str = "desc",
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
                And(*filters),
                sort_by=sort_by,
                order=order,
                page=page,
                items_per_page=items_per_page,
            )
            if filters
            else await self.file_repo.find_many(
                sort_by=sort_by,
                order=order,
                page=page,
                items_per_page=items_per_page,
            )
        )

        total_page = (total_count - 1) // items_per_page + 1
        
        # Document를 FileListResponse로 변환
        file_responses = [FileListResponse.from_document(file) for file in files]
        
        return total_count, total_page, file_responses
    
    def _validate_date_range(self, start_at: Optional[str], end_at: Optional[str]):
        """Validate date range parameters."""
        if end_at and start_at and end_at < start_at:
            raise ValidationError("start_at must be less than end_at")
    
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
    
    def _build_base_filters(self, is_locked: bool, company: Company, type: Type, group_id: Optional[str]) -> list:
        """Build basic filters for company, type, group, and lock status."""
        filters = [
            FileDocument.company == company,
            FileDocument.type == type,
        ]
        if group_id:
            filters.append(FileDocument.group_id == group_id)
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
        now = get_utc_now_naive()
        previous_file = await self.file_repo.find_by_id(id)

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
        await self._record_extra_file_change(
            updated_file_doc.type,
            now,
            previous_file.group_id,
            updated_file_doc.group_id,
        )

        return FileResponse.from_document(updated_file_doc)

    async def _record_extra_file_change(
        self,
        file_type: Type,
        changed_at: datetime,
        *group_ids: str,
    ) -> None:
        if file_type != Type.EXTRA:
            return

        for group_id in set(filter(None, group_ids)):
            await self.group_repo.touch_file_activity(group_id, changed_at)

    async def download_bulk(self, ids: list[str]) -> bytes:
        import io
        import zipfile
        import zlib
        
        # Retrieve files
        files_db = await self.file_repo.find_many(In(FileDocument.id, ids), items_per_page=len(ids))
        files = files_db[1] if isinstance(files_db, tuple) else files_db
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            name_counts = {}
            for file in files:
                if not file.file_name or not file.file_data:
                    continue
                
                name = file.file_name
                # Handle duplicate names
                if name in name_counts:
                    name_counts[name] += 1
                    ext_idx = name.rfind('.')
                    if ext_idx > 0:
                        name = f"{name[:ext_idx]}({name_counts[name]}){name[ext_idx:]}"
                    else:
                        name = f"{name}({name_counts[name]})"
                else:
                    name_counts[name] = 0
                
                try:
                    file_data = zlib.decompress(file.file_data)
                except Exception:
                    file_data = file.file_data
                    
                zip_file.writestr(name, file_data)
                
        return zip_buffer.getvalue()
