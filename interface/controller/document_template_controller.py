from typing import List, Optional, Annotated
from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from application.document_template_service import DocumentTemplateService
from common.auth import CurrentUser, get_current_user
from containers import Container
from domain.document_template import DocumentTemplate, DefaultApprovalStep

router = APIRouter(prefix="/templates", tags=["document-templates"])


class CreateTemplateBody(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    document_prefix: Optional[str] = None
    default_approval_steps: List[DefaultApprovalStep] = []


class UpdateTemplateBody(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    document_prefix: Optional[str] = None
    default_approval_steps: Optional[List[DefaultApprovalStep]] = None
    is_active: Optional[bool] = None


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_template(
    body: CreateTemplateBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    template_service: DocumentTemplateService = Depends(Provide[Container.document_template_service]),
) -> DocumentTemplate:
    """양식 생성 (관리자만 가능)"""
    return await template_service.create_template(
        name=body.name,
        category=body.category,
        current_user_id=current_user.id,
        description=body.description,
        document_prefix=body.document_prefix,
        default_approval_steps=body.default_approval_steps,
    )


@router.get("")
@inject
async def get_templates(
    category: Optional[str] = None,
    active_only: bool = True,
    template_service: DocumentTemplateService = Depends(Provide[Container.document_template_service]),
) -> List[DocumentTemplate]:
    """양식 목록 조회"""
    return await template_service.get_templates(category=category, active_only=active_only)


@router.get("/{template_id}")
@inject
async def get_template(
    template_id: str,
    template_service: DocumentTemplateService = Depends(Provide[Container.document_template_service]),
) -> DocumentTemplate:
    """양식 상세 조회"""
    return await template_service.get_template_by_id(template_id)


@router.put("/{template_id}")
@inject
async def update_template(
    template_id: str,
    body: UpdateTemplateBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    template_service: DocumentTemplateService = Depends(Provide[Container.document_template_service]),
) -> DocumentTemplate:
    """양식 수정 (관리자만 가능)"""
    return await template_service.update_template(
        template_id=template_id,
        current_user_id=current_user.id,
        name=body.name,
        description=body.description,
        category=body.category,
        document_prefix=body.document_prefix,
        default_approval_steps=body.default_approval_steps,
        is_active=body.is_active,
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_template(
    template_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    template_service: DocumentTemplateService = Depends(Provide[Container.document_template_service]),
):
    """양식 삭제 (관리자만 가능)"""
    await template_service.delete_template(template_id, current_user.id)