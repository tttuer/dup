from typing import List, Optional, Dict, Any, Annotated
from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from pydantic import BaseModel

from application.approval_service import ApprovalService
from application.approval_line_service import ApprovalLineService
from common.auth import CurrentUser, get_current_user, DocumentStatus
from containers import Container
from domain.approval_request import ApprovalRequest
from domain.approval_line import ApprovalLine
from domain.responses.paginated_response import PaginatedResponse

router = APIRouter(prefix="/approvals", tags=["approvals"])


class CreateApprovalBody(BaseModel):
    title: str
    content: str
    template_id: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None
    department_id: Optional[str] = None
    approval_lines: Optional[List[Dict[str, Any]]] = None


class ApproveBody(BaseModel):
    comment: Optional[str] = None


class RejectBody(BaseModel):
    comment: Optional[str] = None


class SetApprovalLinesBody(BaseModel):
    approval_lines: List[Dict[str, Any]]


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_approval_request(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    title: str = Form(...),
    content: str = Form(...),
    template_id: Optional[str] = Form(None),
    form_data: Optional[str] = Form(None),  # JSON string
    department_id: Optional[str] = Form(None),
    approval_lines: Optional[str] = Form(None),  # JSON string
    files: List[UploadFile] = File(default=[]),
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> ApprovalRequest:
    """결재 요청 생성 (파일 업로드 포함)"""
    import json

    # JSON 문자열 파싱
    parsed_form_data = json.loads(form_data) if form_data else None
    parsed_approval_lines = json.loads(approval_lines) if approval_lines else None

    # 결재선 필수 체크
    if not parsed_approval_lines:
        raise HTTPException(status_code=400, detail="Approval lines are required")
    
    # 결재 요청 생성 (파일 업로드 및 결재선 설정 포함)
    request = await approval_service.create_approval_request(
        title=title,
        content=content,
        requester_id=current_user.id,
        approval_lines_data=parsed_approval_lines,
        template_id=template_id,
        form_data=parsed_form_data,
        department_id=department_id,
        files=files,
    )

    return request


@router.get("")
@inject
async def get_my_approval_requests(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    sort: Optional[str] = None,  # 정렬 기준: created_at_desc, created_at_asc, updated_at_desc, updated_at_asc
    status: Optional[DocumentStatus] = None,  # 상태 필터
    start_date: Optional[str] = None,  # 시작 날짜 (기안일 기준, YYYY-MM-DD)
    end_date: Optional[str] = None,  # 종료 날짜 (기안일 기준, YYYY-MM-DD)
    page: int = 1,  # 페이지 번호 (1부터 시작)
    page_size: int = 20,  # 페이지당 아이템 수
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> PaginatedResponse[ApprovalRequest]:
    """내가 기안한 결재 목록"""
    items, total = await approval_service.get_my_requests(current_user.id, sort, status, start_date, end_date, page, page_size)
    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/search")
@inject
async def search_approval_requests(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    q: Optional[str] = None,  # 검색어
    status: Optional[str] = None,  # 상태
    start_date: Optional[str] = None,  # 시작 날짜
    end_date: Optional[str] = None,  # 종료 날짜
    skip: int = 0,  # 페이징 시작
    limit: int = 50,  # 페이징 크기
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> List[ApprovalRequest]:
    """전자결재 검색 및 조회"""
    from common.auth import DocumentStatus
    
    # 상태 변환
    status_enum = None
    if status:
        try:
            status_enum = DocumentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    return await approval_service.get_all_approval_requests(
        user_id=current_user.id,
        search_query=q,
        status=status_enum,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )


@router.get("/pending")
@inject
async def get_pending_approvals(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    sort: Optional[str] = None,  # 정렬 기준: created_at_desc, created_at_asc, updated_at_desc, updated_at_asc
    start_date: Optional[str] = None,  # 시작 날짜 (기안일 기준, YYYY-MM-DD)
    end_date: Optional[str] = None,  # 종료 날짜 (기안일 기준, YYYY-MM-DD)
    page: int = 1,  # 페이지 번호 (1부터 시작)
    page_size: int = 20,  # 페이지당 아이템 수
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> PaginatedResponse[ApprovalRequest]:
    """내가 결재할 요청 목록"""
    items, total = await approval_service.get_pending_approvals(current_user.id, sort, start_date, end_date, page, page_size)
    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/completed")
@inject
async def get_completed_approvals(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    sort: Optional[str] = None,  # 정렬 기준: created_at_desc, created_at_asc, completed_at_desc, completed_at_asc
    start_date: Optional[str] = None,  # 시작 날짜 (결재완료일 기준, YYYY-MM-DD)
    end_date: Optional[str] = None,  # 종료 날짜 (결재완료일 기준, YYYY-MM-DD)
    page: int = 1,  # 페이지 번호 (1부터 시작)
    page_size: int = 20,  # 페이지당 아이템 수
    approval_service: ApprovalService = Depends(Provide[Container.approval_service]),
) -> PaginatedResponse[ApprovalRequest]:
    """내가 결재 완료한 목록"""
    items, total = await approval_service.get_completed_approvals(current_user.id, sort, start_date, end_date, page, page_size)
    return PaginatedResponse.create(items, total, page, page_size)


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
    line_service: ApprovalLineService = Depends(
        Provide[Container.approval_line_service]
    ),
) -> List[ApprovalLine]:
    """결재선 조회"""
    return await line_service.get_approval_lines(request_id, current_user.id)


@router.put("/{request_id}/lines")
@inject
async def set_approval_lines(
    request_id: str,
    body: SetApprovalLinesBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    line_service: ApprovalLineService = Depends(
        Provide[Container.approval_line_service]
    ),
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
