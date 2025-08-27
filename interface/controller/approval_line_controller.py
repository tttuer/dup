from typing import List, Annotated, Optional
from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from application.approval_line_service import ApprovalLineService
from application.approval_favorite_group_service import ApprovalFavoriteGroupService
from common.auth import CurrentUser, get_current_user
from containers import Container
from domain.approval_line import ApprovalLine
from domain.approval_favorite_group import ApprovalFavoriteGroup

router = APIRouter(prefix="/approval-lines", tags=["approval-lines"])


class AddApprovalLineBody(BaseModel):
    request_id: str
    approver_id: str
    step_order: int
    is_required: bool = True
    is_parallel: bool = False


class CreateFavoriteGroupBody(BaseModel):
    name: str
    approver_ids: List[str]


class UpdateFavoriteGroupBody(BaseModel):
    name: Optional[str] = None
    approver_ids: Optional[List[str]] = None


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


# 즐겨찾기 그룹 관련 API
@router.post("/favorite-groups", status_code=status.HTTP_201_CREATED)
@inject
async def create_favorite_group(
    body: CreateFavoriteGroupBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: ApprovalFavoriteGroupService = Depends(Provide[Container.approval_favorite_group_service]),
) -> ApprovalFavoriteGroup:
    """즐겨찾기 그룹 생성"""
    return await service.create_favorite_group(
        user_id=current_user.id,
        name=body.name,
        approver_ids=body.approver_ids,
    )


@router.get("/favorite-groups")
@inject
async def get_my_favorite_groups(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: ApprovalFavoriteGroupService = Depends(Provide[Container.approval_favorite_group_service]),
) -> List[ApprovalFavoriteGroup]:
    """내 즐겨찾기 그룹 목록 조회"""
    return await service.get_user_favorite_groups(current_user.id)


@router.get("/favorite-groups/{group_id}")
@inject
async def get_favorite_group(
    group_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: ApprovalFavoriteGroupService = Depends(Provide[Container.approval_favorite_group_service]),
) -> ApprovalFavoriteGroup:
    """즐겨찾기 그룹 상세 조회"""
    return await service.get_favorite_group_by_id(group_id, current_user.id)


@router.patch("/favorite-groups/{group_id}")
@inject
async def update_favorite_group(
    group_id: str,
    body: UpdateFavoriteGroupBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: ApprovalFavoriteGroupService = Depends(Provide[Container.approval_favorite_group_service]),
) -> ApprovalFavoriteGroup:
    """즐겨찾기 그룹 수정"""
    return await service.update_favorite_group(
        group_id=group_id,
        user_id=current_user.id,
        name=body.name,
        approver_ids=body.approver_ids,
    )


@router.delete("/favorite-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_favorite_group(
    group_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: ApprovalFavoriteGroupService = Depends(Provide[Container.approval_favorite_group_service]),
):
    """즐겨찾기 그룹 삭제"""
    await service.delete_favorite_group(group_id, current_user.id)


@router.post("/favorite-groups/{group_id}/apply-to-request")
@inject
async def apply_favorite_group_to_request(
    group_id: str,
    request_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    favorite_service: ApprovalFavoriteGroupService = Depends(Provide[Container.approval_favorite_group_service]),
    line_service: ApprovalLineService = Depends(Provide[Container.approval_line_service]),
) -> List[ApprovalLine]:
    """즐겨찾기 그룹을 결재선에 적용"""
    group = await favorite_service.get_favorite_group_by_id(group_id, current_user.id)
    
    # 현재 결재선의 최대 순서 확인
    existing_lines = await line_service.get_approval_lines(request_id, current_user.id)
    max_order = max([line.step_order for line in existing_lines], default=0)
    
    # 그룹의 모든 결재자 데이터를 한 번에 준비
    approver_data = []
    for i, approver_id in enumerate(group.approver_ids):
        approver_data.append({
            "approver_id": approver_id,
            "step_order": max_order + i + 1,
            "is_required": True,
            "is_parallel": False,
        })
    
    # 모든 결재자를 한 번에 추가
    return await line_service.bulk_add_approval_lines(
        request_id=request_id,
        requester_id=current_user.id,
        approver_data=approver_data,
    )