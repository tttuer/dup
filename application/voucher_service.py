import zlib
from datetime import datetime
from typing import Optional, List

from beanie.operators import And, RegEx, Or, In
from dependency_injector.wiring import inject
from fastapi import UploadFile, HTTPException
from ulid import ULID

from common.auth import Role
from domain.voucher import Voucher, Company, SearchOption
from domain.repository.voucher_repo import IVoucherRepository
from infra.db_models.voucher import Voucher as VoucherDocument


class VoucherService:
    @inject
    def __init__(self, voucher_repo: IVoucherRepository):
        self.voucher_repo = voucher_repo
        self.ulid = ULID()

    async def compress_pdf(self, file_data: UploadFile) -> bytes:
        raw_data = await file_data.read()
        compress_data = zlib.compress(raw_data)
        return compress_data

    async def save_vouchers(
        self,
        withdrawn_at: str,
        name: str,
        price: int,
        company: Company,
        file_datas: list[UploadFile],
        lock: bool,
    ):
        now = datetime.now()
        vouchers: list[Voucher] = [
            Voucher(
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

        await self.voucher_repo.save_all(vouchers)

        return vouchers

    async def find_by_id(self, id: str):
        voucher = await self.voucher_repo.find_by_id(id)

        return voucher

    async def find_many(
        self,
        is_locked: bool,
        role: Role,
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

        total_count, vouchers = (
            await self.voucher_repo.find_many(
                And(*filters), page=page, items_per_page=items_per_page
            )
            if filters
            else await self.voucher_repo.find_many(
                page=page, items_per_page=items_per_page
            )
        )

        total_page = (total_count - 1) // items_per_page + 1

        return total_count, total_page, vouchers

    async def delete(self, id: str):
        await self.voucher_repo.delete(id)

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

        voucher: Voucher = Voucher(
            id=id,
            withdrawn_at=withdrawn_at,
            name=name,
            price=price,
            updated_at=now,
        )

        update_voucher = await self.voucher_repo.update(voucher)

        return update_voucher
