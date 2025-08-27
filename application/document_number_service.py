from datetime import datetime, timezone
from typing import Optional
from dependency_injector.wiring import inject
from ulid import ULID

from application.base_service import BaseService
from domain.repository.document_template_repo import IDocumentTemplateRepository
from domain.repository.approval_request_repo import IApprovalRequestRepository
from domain.repository.user_repo import IUserRepository
from utils.time import get_utc_now_naive


class DocumentNumberService(BaseService):
    @inject
    def __init__(
        self,
        template_repo: IDocumentTemplateRepository,
        approval_repo: IApprovalRequestRepository,
        user_repo: IUserRepository,
    ):
        super().__init__(user_repo)
        self.template_repo = template_repo
        self.approval_repo = approval_repo
        self.ulid = ULID()

    async def generate_document_number(
        self,
        template_id: str,
        department_code: Optional[str] = None,
    ) -> str:
        """
        문서번호 생성
        형식: {양식프리픽스}-{년도}-{부서코드}-{일련번호}
        예시: 업무기안-2025-MGT-000001
        """
        template = await self.template_repo.find_by_id(template_id)
        if not template:
            raise ValueError("Template not found")

        now = get_utc_now_naive()
        year = now.year
        
        # 프리픽스 결정
        prefix = template.document_prefix or template.name
        
        # 부서코드 (없으면 DEFAULT 사용)
        dept_code = department_code or "DEFAULT"
        
        # 오늘 날짜로 일련번호 생성 (간단한 구현)
        # 실제로는 Redis나 별도 시퀀스 테이블을 사용하는 것이 좋음
        serial = self.ulid.generate()[:6].upper()
        
        return f"{prefix}-{year}-{dept_code}-{serial}"

    async def get_next_document_number(
        self,
        template_id: str,
        department_code: Optional[str] = None,
    ) -> str:
        """다음 문서번호 미리보기"""
        return await self.generate_document_number(template_id, department_code)

    async def validate_document_number(self, document_number: str) -> bool:
        """문서번호 중복 확인"""
        existing = await self.approval_repo.find_by_document_number(document_number)
        return existing is None