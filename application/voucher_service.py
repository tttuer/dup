from datetime import datetime, timezone
from typing import Optional, List

from beanie.operators import And, RegEx
from dependency_injector.wiring import inject
from fastapi import UploadFile, HTTPException
from ulid import ULID

from domain.voucher import Company, SearchOption, VoucherFile
from domain.repository.voucher_repo import IVoucherRepository
from infra.db_models.voucher import Voucher as VoucherDocument
from domain.responses.voucher_response import VoucherResponse
from utils.pdf import Pdf
from utils.whg import Whg
import asyncio
from anyio import to_thread


class VoucherService:
    @inject
    def __init__(self, voucher_repo: IVoucherRepository):
        self.voucher_repo = voucher_repo
        self.ulid = ULID()

    async def sync(
        self,
        year: int,
        company: Company = Company.BAEKSUNG,
        wehago_id: str = None,
        wehago_password: str = None,
    ):
        # 🧵 크롤링을 별도 쓰레드에서 실행
        vouchers = await to_thread.run_sync(
            lambda: Whg().crawl_whg(company, year, wehago_id, wehago_password)
        )

        for v in vouchers:
            v.company = company

        # 3. 새로 수집한 ID 목록
        new_ids = {v.id for v in vouchers}

        # 4. 기존 DB에 저장된 ID 목록 조회
        existing_vouchers = await self.voucher_repo.find_by_company_and_year(
            company, year
        )
        existing_ids = {v.id for v in existing_vouchers}

        # 5. 삭제 대상 ID 찾기 (기존에는 있었는데, 새로는 없음)
        ids_to_delete = existing_ids - new_ids

        if ids_to_delete:
            await self.voucher_repo.delete_by_ids(ids_to_delete)

        await self.voucher_repo.save(vouchers)

        return vouchers

    async def find_by_id(self, id: str) -> VoucherResponse:
        voucher_doc = await self.voucher_repo.find_by_id(id)

        return VoucherResponse.from_document(voucher_doc)

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

        # Document를 VoucherResponse로 변환
        voucher_responses = [VoucherResponse.from_document(voucher) for voucher in vouchers]
        
        return total_count, total_page, voucher_responses

    async def update(
        self, id: str, items: list[tuple[Optional[str], Optional[UploadFile]]]
    ) -> VoucherResponse:
        voucher_doc = await self.voucher_repo.find_by_id(id)

        for file_id, upload_file in items:
            # 삭제 또는 교체 (file_id 있는 경우)
            if file_id:
                voucher_doc.files = [f for f in voucher_doc.files if f.file_id != file_id] if voucher_doc.files else []
                if len(voucher_doc.files) == 0:
                    voucher_doc.files = None

            # 추가 또는 교체 (파일 있는 경우)
            if upload_file:
                if voucher_doc.files is None:
                    voucher_doc.files = []
                
                # VoucherFile 객체로 저장
                voucher_file = VoucherFile(
                    file_name=upload_file.filename,
                    file_data=await Pdf.compress(upload_file),
                    uploaded_at=datetime.now(timezone.utc),
                )
                voucher_doc.files.append(voucher_file)

        # Document를 직접 저장
        updated_voucher_doc = await voucher_doc.save()
        return VoucherResponse.from_document(updated_voucher_doc)
