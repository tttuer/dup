import json
from typing import Annotated, List, Optional

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from application.payment_task_service import PaymentTaskService
from common.auth import CurrentUser, get_current_user
from containers import Container


router = APIRouter(prefix="/payment-tasks", tags=["payment-tasks"])


class SetPaymentDueDateBody(BaseModel):
    due_date: str


@router.post("")
@inject
async def create_direct_payment_task(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    assignee_id: str = Form(...),
    name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    amount: Optional[int] = Form(None),
    due_date: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    """결재선 없이 납부 담당자에게 바로 전달되는 요청을 생성한다."""
    return await payment_task_service.create_direct_payment_task(
        current_user.id,
        {
            "assignee_id": assignee_id,
            "name": name,
            "category": category,
            "amount": amount,
            "due_date": due_date,
            "description": description,
        },
        files,
    )


@router.get("/my")
@inject
async def get_my_payment_tasks(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    status: Optional[str] = None,
    limit: int = 100,
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    """현재 사용자가 납부 담당자인 후속 업무 목록."""
    return await payment_task_service.get_my_tasks(current_user.id, status, min(max(limit, 1), 100))


@router.get("/summary")
@inject
async def get_my_payment_task_summary(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    """사이드바 배지에 표시할 오늘 납부·요청 확인 건수."""
    return await payment_task_service.get_my_summary(current_user.id)


@router.get("/{task_id}")
@inject
async def get_payment_task(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    """요청자·담당자·관리자만 딥링크로 납부 업무를 조회한다."""
    return await payment_task_service.get_task(task_id, current_user.id, current_user.roles)


@router.patch("/{task_id}/due-date")
@inject
async def set_payment_task_due_date(
    task_id: str,
    body: SetPaymentDueDateBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    return await payment_task_service.set_due_date(task_id, current_user.id, body.due_date)


@router.post("/{task_id}/confirm")
@inject
async def confirm_payment_task_request(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    """납부 담당자가 요청 내용을 확인하고 요청자 수정을 잠근다."""
    return await payment_task_service.confirm_direct_request(task_id, current_user.id)


@router.patch("/{task_id}")
@inject
async def update_direct_payment_task(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    assignee_id: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    amount: Optional[int] = Form(None),
    due_date: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    deleted_file_ids: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    updates = {
        key: value for key, value in {
            "assignee_id": assignee_id,
            "name": name,
            "category": category,
            "amount": amount,
            "due_date": due_date,
            "description": description,
        }.items() if value is not None
    }
    return await payment_task_service.update_direct_request(
        task_id,
        current_user.id,
        updates,
        files,
        json.loads(deleted_file_ids) if deleted_file_ids else [],
    )


@router.patch("/{task_id}/completion")
@inject
async def update_payment_task_completion(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    paid_at: Optional[str] = Form(None),
    paid_amount: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    deleted_file_ids: Optional[str] = Form(None),
    receipt_files: List[UploadFile] = File(default=[]),
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    """납부 완료 뒤 담당자가 실제 납부 결과와 증빙을 수정한다."""
    return await payment_task_service.update_completion(
        task_id,
        current_user.id,
        paid_at,
        paid_amount,
        note,
        receipt_files,
        json.loads(deleted_file_ids) if deleted_file_ids else [],
    )


@router.get("/{task_id}/files")
@inject
async def get_payment_task_files(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    return await payment_task_service.get_task_files(task_id, current_user.id, current_user.roles)


@router.get("/{task_id}/files/{file_id}/download")
@inject
async def download_payment_task_file(
    task_id: str,
    file_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    return await payment_task_service.download_task_file(
        task_id, file_id, current_user.id, current_user.roles
    )


@router.post("/{task_id}/complete")
@inject
async def complete_payment_task(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    paid_at: str = Form(...),
    paid_amount: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    receipt_files: List[UploadFile] = File(default=[]),
    payment_task_service: PaymentTaskService = Depends(Provide[Container.payment_task_service]),
):
    """실제 납부 결과와 납부확인증을 등록한다."""
    return await payment_task_service.complete_task(
        task_id, current_user.id, paid_at, paid_amount, note, receipt_files
    )
