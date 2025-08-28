from datetime import datetime, timezone
from typing import List, Optional
from dependency_injector.wiring import inject
from fastapi import HTTPException
from ulid import ULID

from application.base_service import BaseService
from domain.repository.document_template_repo import IDocumentTemplateRepository
from domain.repository.user_repo import IUserRepository
from domain.document_template import DocumentTemplate, DefaultApprovalStep
from common.auth import Role
from utils.time import get_utc_now_naive, utc_to_kst_naive


class DocumentTemplateService(BaseService[DocumentTemplate]):
    @inject
    def __init__(self, template_repo: IDocumentTemplateRepository, user_repo: IUserRepository):
        super().__init__(user_repo)
        self.template_repo = template_repo
        self.ulid = ULID()

    async def create_template(
        self,
        name: str,
        category: str,
        current_user_id: str,
        description: Optional[str] = None,
        document_prefix: Optional[str] = None,
        default_approval_steps: Optional[List[DefaultApprovalStep]] = None,
    ) -> DocumentTemplate:
        # 관리자 권한 확인
        user = await self.validate_user_exists(current_user_id)
        if Role.ADMIN not in user.roles:
            raise HTTPException(status_code=403, detail="Admin privileges required")

        # 필수 필드 검증
        name = self.validate_required_field(name, "Template name")
        category = self.validate_required_field(category, "Category")

        now = get_utc_now_naive()
        template = DocumentTemplate(
            id=self.ulid.generate(),
            name=name,
            description=description,
            category=category,
            document_prefix=document_prefix,
            default_approval_steps=default_approval_steps or [],
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        await self.template_repo.save(template)
        return template

    async def get_templates(self, category: Optional[str] = None, active_only: bool = True) -> List[DocumentTemplate]:
        if category:
            templates = await self.template_repo.find_by_category(category)
            if active_only:
                templates = [t for t in templates if t.is_active]
        elif active_only:
            templates = await self.template_repo.find_active_templates()
        else:
            templates = await self.template_repo.find_all()
        
        return templates

    async def get_template_by_id(self, template_id: str) -> DocumentTemplate:
        template = await self.template_repo.find_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template

    async def update_template(
        self,
        template_id: str,
        current_user_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        document_prefix: Optional[str] = None,
        default_approval_steps: Optional[List[DefaultApprovalStep]] = None,
        is_active: Optional[bool] = None,
    ) -> DocumentTemplate:
        # 관리자 권한 확인
        user = await self.validate_user_exists(current_user_id)
        if Role.ADMIN not in user.roles:
            raise HTTPException(status_code=403, detail="Admin privileges required")

        template = await self.get_template_by_id(template_id)
        
        if name is not None:
            template.name = self.validate_required_field(name, "Template name")
        if description is not None:
            template.description = description
        if category is not None:
            template.category = self.validate_required_field(category, "Category")
        if document_prefix is not None:
            template.document_prefix = document_prefix
        if default_approval_steps is not None:
            template.default_approval_steps = default_approval_steps
        if is_active is not None:
            template.is_active = is_active
        
        template.updated_at = get_utc_now_naive()
        
        updated_template = await self.template_repo.update(template)
        
        # UTC → KST 변환
        updated_template.created_at = utc_to_kst_naive(updated_template.created_at)
        updated_template.updated_at = utc_to_kst_naive(updated_template.updated_at)
        
        return updated_template

    async def delete_template(self, template_id: str, current_user_id: str) -> None:
        # 관리자 권한 확인
        user = await self.validate_user_exists(current_user_id)
        if Role.ADMIN not in user.roles:
            raise HTTPException(status_code=403, detail="Admin privileges required")

        template = await self.get_template_by_id(template_id)
        await self.template_repo.delete(template_id)