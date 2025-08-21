from typing import List, Optional, Dict, Any, Annotated
from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from application.approval_service import ApprovalService
from application.approval_line_service import ApprovalLineService
from common.auth import CurrentUser, get_current_user, DocumentVisibility
from containers import Container
from domain.approval_request import ApprovalRequest
from domain.approval_line import ApprovalLine

router = APIRouter(prefix="/approvals", tags=["approvals"])


class CreateApprovalBody(BaseModel):
    title: str
    content: str
    template_id: Optional[str] = None
    visibility: DocumentVisibility = DocumentVisibility.PRIVATE
    form_data: Optional[Dict[str, Any]] = None
    department_id: Optional[str] = None


class ApproveBody(BaseModel):
    comment: Optional[str] = None


class RejectBody(BaseModel):
    comment: Optional[str] = None


class SetApprovalLinesBody(BaseModel):
    approval_lines: List[Dict[str, Any]]


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_approval_request(
    body: CreateApprovalBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> ApprovalRequest:
    """결재 요청 생성"""
    return await approval_service.create_approval_request(
        title=body.title,
        content=body.content,
        requester_id=current_user.id,
        template_id=body.template_id,
        visibility=body.visibility,
        form_data=body.form_data,
        department_id=body.department_id,
    )


@router.get("")
@inject
async def get_my_approval_requests(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> List[ApprovalRequest]:
    """내가 기안한 결재 목록"""
    return await approval_service.get_my_requests(current_user.id)


@router.get("/pending")
@inject
async def get_pending_approvals(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> List[ApprovalRequest]:
    """내가 결재할 요청 목록"""
    return await approval_service.get_pending_approvals(current_user.id)


@router.get("/{request_id}")
@inject
async def get_approval_request(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> ApprovalRequest:
    """결재 요청 상세 조회"""
    return await approval_service.get_request_by_id(request_id, current_user.id)


@router.post("/{request_id}/submit")
@inject
async def submit_approval_request(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> ApprovalRequest:
    """결재 요청 상신"""
    return await approval_service.submit_approval_request(request_id, current_user.id)


@router.post("/{request_id}/approve")
@inject
async def approve_request(
    request_id: str,
    body: ApproveBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> ApprovalRequest:
    """결재 승인"""
    return await approval_service.approve_request(
        request_id=request_id,
        approver_id=current_user.id,
        comment=body.comment,
    )


@router.post("/{request_id}/reject")
@inject
async def reject_request(
    request_id: str,
    body: RejectBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> ApprovalRequest:
    """결재 반려"""
    return await approval_service.reject_request(
        request_id=request_id,
        approver_id=current_user.id,
        comment=body.comment,
    )


@router.post("/{request_id}/cancel")
@inject
async def cancel_request(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> ApprovalRequest:
    """결재 요청 취소"""
    return await approval_service.cancel_request(request_id, current_user.id)


@router.get("/{request_id}/lines")
@inject
async def get_approval_lines(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    line_service: ApprovalLineService = Depends(Provide[Container.approval_line_service]),
) -> List[ApprovalLine]:
    """결재선 조회"""
    return await line_service.get_approval_lines(request_id, current_user.id)


@router.put("/{request_id}/lines")
@inject
async def set_approval_lines(
    request_id: str,
    body: SetApprovalLinesBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    line_service: ApprovalLineService = Depends(Provide[Container.approval_line_service]),
) -> List[ApprovalLine]:
    """결재선 설정"""
    return await line_service.set_approval_lines(
        request_id=request_id,
        requester_id=current_user.id,
        approval_lines_data=body.approval_lines,
    )


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_approval_request(
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
):
    """결재 요청 삭제 (임시저장만 가능)"""
    # 임시저장 상태의 요청만 삭제 가능하도록 서비스 레이어에서 검증
    await approval_service.cancel_request(request_id, current_user.id)