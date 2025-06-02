from fastapi import APIRouter, Depends
from dependency_injector.wiring import inject, Provide
from application.sync_service import SyncService
from application.websocket_manager import WebSocketManager
from common.auth import CurrentUser
from containers import Container
from typing import Annotated
from common.auth import get_current_user
from application.voucher_service import VoucherService
from domain.voucher import Company, VoucherFile
from fastapi import UploadFile
from pydantic import BaseModel, model_validator, field_serializer
import zlib
import base64
from typing import Optional, List
from fastapi import Form
from datetime import datetime
from itertools import zip_longest
from fastapi import File

router = APIRouter(prefix="/vouchers", tags=["voucher"])


class VoucherResponse(BaseModel):
    id: str
    mn_bungae1: Optional[float] = None
    mn_bungae2: Optional[float] = None
    nm_remark: Optional[str] = None
    sq_acttax2: Optional[int] = None
    nm_gubn: Optional[str] = None
    cd_acctit: Optional[str] = None
    year: Optional[str] = None
    cd_trade: Optional[str] = None
    dt_time: Optional[datetime] = None
    month: Optional[str] = None
    day: Optional[str] = None
    nm_acctit: Optional[str] = None
    dt_insert: Optional[datetime] = None
    user_id: Optional[str] = None
    da_date: Optional[str] = None
    nm_trade: Optional[str] = None
    no_acct: Optional[int] = None
    voucher_date: Optional[str] = None
    files: Optional[list[VoucherFile]] = None
    company: Optional[Company] = None


class SyncRequest(BaseModel):
    year: int = datetime.now().year
    company: Company = Company.BAEKSUNG


@router.post("/sync")
@inject
async def sync_whg(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    sync_request: SyncRequest,
    ws_manager: WebSocketManager = Depends(Provide[Container.websocket_manager]),
    sync_service: SyncService = Depends(Provide[Container.sync_service]),
    voucher_service: VoucherService = Depends(Provide[Container.voucher_service]),
):
    await sync_service.set_sync_status(True)
    # ✅ 동기화 시작 알림
    await ws_manager.broadcast({"syncing": True})
    await voucher_service.sync(company=sync_request.company, year=sync_request.year)
    # ✅ 동기화 종료 알림
    await ws_manager.broadcast({"syncing": False})
    return {"message": "Sync completed successfully"}


@router.get("/{id}")
@inject
async def find_voucher(
    id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    voucher_service: VoucherService = Depends(Provide[Container.voucher_service]),
) -> VoucherResponse:
    return await voucher_service.find_by_id(id)


@router.patch("/{id}")
@inject
async def update_voucher(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    id: str,
    file_ids: Optional[List[Optional[str]]] = Form(None),
    files: Optional[List[UploadFile]] = File(
        None
    ),  # ✅ UploadFile만 허용하면 Swagger에서 파일 UI가 뜸
    voucher_service: VoucherService = Depends(Provide[Container.voucher_service]),
) -> VoucherResponse:
    update_items = list(
        zip_longest(file_ids or [], files or [])
    )  # ✅ 길이 다를 수 있음
    return await voucher_service.update(id=id, items=update_items)


@router.get("")
@inject
async def find_vouchers(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    search: Optional[str] = None,
    search_option: Optional[str] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    company: Optional[Company] = Company.BAEKSUNG,
    page: int = 1,
    items_per_page: int = 20,
    voucher_service: VoucherService = Depends(Provide[Container.voucher_service]),
) -> tuple[int, int, list[VoucherResponse]]:
    return await voucher_service.find_many(
        search=search,
        search_option=search_option,
        company=company,
        start_at=start_at,
        end_at=end_at,
        page=page,
        items_per_page=items_per_page,
    )
