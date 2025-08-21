from typing import List, Annotated
from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from application.approval_line_service import ApprovalLineService
from common.auth import CurrentUser, get_current_user
from containers import Container
from domain.approval_line import ApprovalLine

router = APIRouter(prefix="/approval-lines", tags=["approval-lines"])


class AddApprovalLineBody(BaseModel):
    request_id: str
    approver_id: str
    step_order: int
    is_required: bool = True
    is_parallel: bool = False


@router.get("/my-pending")
@inject
async def get_my_pending_approvals(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    line_service: ApprovalLineService = Depends(Provide[Container.approval_line_service]),
) -> List[ApprovalLine]:
    """내가 결재해야 할 요청들"""
    return await line_service.get_my_pending_approvals(current_user.id)


@router.get("/my-history")
@inject
async def get_my_approval_history(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    line_service: ApprovalLineService = Depends(Provide[Container.approval_line_service]),
) -> List[ApprovalLine]:
    """내 결재 이력"""
    return await line_service.get_my_approval_history(current_user.id)


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def add_approval_line(
    body: AddApprovalLineBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    line_service: ApprovalLineService = Depends(Provide[Container.approval_line_service]),
) -> ApprovalLine:
    """결재선에 결재자 추가"""
    return await line_service.add_approval_line(
        request_id=body.request_id,
        requester_id=current_user.id,
        approver_id=body.approver_id,
        step_order=body.step_order,
        is_required=body.is_required,
        is_parallel=body.is_parallel,
    )


@router.delete("/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def remove_approval_line(
    line_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    line_service: ApprovalLineService = Depends(Provide[Container.approval_line_service]),
):
    """결재선에서 결재자 제거"""
    await line_service.remove_approval_line(line_id, current_user.id)