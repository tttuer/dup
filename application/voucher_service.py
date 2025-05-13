from datetime import datetime, timezone
from typing import Optional, List

from beanie.operators import And, RegEx
from dependency_injector.wiring import inject
from fastapi import UploadFile, HTTPException
from ulid import ULID

from domain.voucher import Company, SearchOption, VoucherFile
from domain.repository.voucher_repo import IVoucherRepository
from infra.db_models.voucher import Voucher as VoucherDocument
from utils.pdf import Pdf
from utils.whg import Whg


class VoucherService:
    @inject
    def __init__(self, voucher_repo: IVoucherRepository):
        self.voucher_repo = voucher_repo
        self.ulid = ULID()

    async def save_vouchers(
        self,
        company: Company = Company.BAEKSUNG,
    ):
        vouchers = await Whg.crawl_whg(company)

        for v in vouchers:
            v.company = company

        await self.voucher_repo.save(vouchers)

        return vouchers

    async def find_by_id(self, id: str):
        voucher = await self.voucher_repo.find_by_id(id)

        return voucher

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
            if search_option == SearchOption.NM_ACCTIT:
                filters.append(
                    RegEx(VoucherDocument.nm_acctit, f".*{search}.*", options="i")
                )
            elif search_option == SearchOption.NM_TRADE:
                filters.append(
                    RegEx(VoucherDocument.nm_trade, f".*{search}.*", options="i")
                )
            elif search_option == SearchOption.NM_REMARK:
                filters.append(
                    RegEx(VoucherDocument.nm_remark, f".*{search}.*", options="i")
                )

        filters.append(VoucherDocument.company == company)

        if start_at and end_at:
            filters.append(VoucherDocument.voucher_date >= start_at)
            filters.append(VoucherDocument.voucher_date <= end_at)
        if start_at:
            filters.append(VoucherDocument.voucher_date >= start_at)

        if end_at and start_at and end_at < start_at:
            raise HTTPException(
                status_code=400,
                detail="start_at must be less than end_at",
            )

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

    async def update(
        self,
        id: str,
        items: list[tuple[Optional[str], Optional[UploadFile]]]
    ):
        voucher = await self.voucher_repo.find_by_id(id)

        for file_id, upload_file in items:
            # 삭제 또는 교체 (file_id 있는 경우)
            if file_id:
                voucher.files = [f for f in voucher.files if f.file_id != file_id]

            # 추가 또는 교체 (파일 있는 경우)
            if upload_file:
                voucher.files.append(VoucherFile(
                    file_name=upload_file.filename,
                    file_data=await Pdf.compress(upload_file),
                    uploaded_at=datetime.now(timezone.utc)
                ))

        return await self.voucher_repo.update(voucher)
