from io import BytesIO
from typing import Optional
import zipfile

from beanie.operators import And, RegEx, In
from dependency_injector.wiring import inject
from fastapi import UploadFile
from ulid import ULID

from common.exceptions import ValidationError
from domain.repository.voucher_repo import IVoucherRepository
from domain.responses.voucher_response import VoucherResponse
from domain.voucher import Company, SearchOption, VoucherFile
from infra.db_models.voucher import Voucher as VoucherDocument
from utils.pdf import Pdf
from utils.time import get_utc_now_naive
from utils.whg import Whg


class VoucherService:
    @inject
    def __init__(self, voucher_repo: IVoucherRepository):
        self.voucher_repo = voucher_repo
        self.ulid = ULID()

    async def sync(
        self,
        year: int,
        month: int = None,
        company: Company = Company.BAEKSUNG,
        wehago_id: str = None,
        wehago_password: str = None,
    ):
        # 🚀 async 크롤링 직접 실행 (병렬 처리)
        vouchers = await Whg().crawl_whg(company, year, month, wehago_id, wehago_password)

        # 3. 새로 수집한 ID 목록
        new_ids = {v.id for v in vouchers}

        # 4. 기존 DB에 저장된 ID 목록 조회
        if month is None:
            # month가 None이면 연도 전체 조회
            existing_vouchers = await self.voucher_repo.find_by_company_and_year(
                company, year
            )
        else:
            # month가 있으면 해당 월만 조회
            existing_vouchers = await self.voucher_repo.find_by_company_year_and_month(
                company, year, month
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
        items_per_page: int = 1000,
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
            raise ValidationError("start_at must be less than end_at")

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
                    uploaded_at=get_utc_now_naive(),
                )
                voucher_doc.files.append(voucher_file)

        # Document를 직접 저장
        updated_voucher_doc = await voucher_doc.save()
        
        return VoucherResponse.from_document(updated_voucher_doc)

    async def download_files(self, file_ids: list[str]) -> bytes:
        unique_file_ids = list(dict.fromkeys(file_ids))
        if not unique_file_ids:
            raise ValidationError("file_ids is required")

        vouchers = await VoucherDocument.find(
            {"files.file_id": {"$in": unique_file_ids}}
        ).to_list()
        files_by_id = {
            file.file_id: file
            for voucher in vouchers
            for file in voucher.files or []
            if file.file_id in unique_file_ids
        }

        if not files_by_id:
            raise ValidationError("No voucher files found")

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_id in unique_file_ids:
                file = files_by_id.get(file_id)
                if file:
                    zip_file.writestr(file.file_name, file.file_data)

        return zip_buffer.getvalue()

    async def migrate_voucher_ids(self) -> int:
        """
        잘못 저장된 voucher ID를 올바른 {sq_acttax2}_{company} 형식으로 변경
        기존 데이터는 보존되며, 새로운 ID로 복사 후 기존 ID 삭제
        """
        # 모든 voucher 조회
        all_vouchers = await VoucherDocument.find_all().to_list()
        
        migrated_count = 0
        vouchers_to_delete = []
        vouchers_to_create = []
        
        for voucher in all_vouchers:
            # 현재 ID가 올바른 형식인지 확인
            if voucher.company and voucher.sq_acttax2:
                correct_id = f"{voucher.sq_acttax2}_{voucher.company.value}"
                
                # 이미 올바른 형식이면 건너뛰기
                if voucher.id == correct_id:
                    continue
                
                # 잘못된 형식인지 확인 (예: {company}_{sq_acttax2} 또는 다른 형식)
                wrong_format_id = f"{voucher.company.value}_{voucher.sq_acttax2}"
                if voucher.id == wrong_format_id or voucher.id != correct_id:
                    # 올바른 ID로 복사할 데이터 준비
                    voucher_dict = voucher.model_dump()
                    voucher_dict["id"] = correct_id
                    
                    # 새로운 voucher 문서 생성
                    new_voucher = VoucherDocument(**voucher_dict)
                    vouchers_to_create.append(new_voucher)
                    
                    # 기존 voucher 삭제 목록에 추가
                    vouchers_to_delete.append(voucher.id)
                    
                    migrated_count += 1
        
        # 새로운 voucher들 일괄 생성
        if vouchers_to_create:
            await VoucherDocument.insert_many(vouchers_to_create)
        
        # 기존 voucher들 일괄 삭제
        if vouchers_to_delete:
            await VoucherDocument.find(In(VoucherDocument.id, vouchers_to_delete)).delete()
        
        return migrated_count
