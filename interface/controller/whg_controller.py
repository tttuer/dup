import json
from datetime import datetime
from itertools import zip_longest
from typing import Annotated
from typing import Optional, List

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends
from fastapi import File
from fastapi import Form
from fastapi import UploadFile
from pydantic import BaseModel
from redis.asyncio import Redis

from application.sync_service import SyncService
from application.voucher_service import VoucherService
from common.auth import CurrentUser
from common.auth import get_current_user
from common.exceptions import InternalServerError
from containers import Container
from domain.responses.voucher_response import VoucherResponse
from domain.voucher import Company

router = APIRouter(prefix="/vouchers", tags=["voucher"])




class SyncRequest(BaseModel):
    wehago_id: str
    wehago_password: str
    month: int = None
    year: int = datetime.now().year
    company: Company = Company.BAEKSUNG


@router.post("/sync")
@inject
async def sync_whg(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    sync_request: SyncRequest,
    sync_service: SyncService = Depends(Provide[Container.sync_service]),
    voucher_service: VoucherService = Depends(Provide[Container.voucher_service]),
    redis: Redis = Depends(Provide[Container.redis]),
):
    # ✅ 상태 업데이트 + Redis Pub/Sub 전파만 수행
    await sync_service.set_sync_status(True)
    await redis.publish("sync_status_channel", json.dumps({"syncing": True}))

    try:
        await voucher_service.sync(
            company=sync_request.company,
            year=sync_request.year,
            month=sync_request.month,
            wehago_id=sync_request.wehago_id,
            wehago_password=sync_request.wehago_password,
        )
        return {"message": "Sync completed successfully"}
    except Exception as e:
        raise InternalServerError(f"동기화 오류: {e}")
    finally:
        await sync_service.set_sync_status(False)
        await redis.publish("sync_status_channel", json.dumps({"syncing": False}))


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
    ),  # ✅ UploadFile만 허용ㅇ하면 Swagger에서 파일 UI가 뜸
    voucher_service: VoucherService = Depends(Provide[Container.voucher_service]),
) -> VoucherResponse:
    update_items = list(
        zip_longest(file_ids or [], files or [])
    )  # ✅ 길이 다를 수 있음
    return await voucher_service.update(id=id, items=update_items)


@router.post("/migrate-ids")
@inject
async def migrate_voucher_ids(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    voucher_service: VoucherService = Depends(Provide[Container.voucher_service]),
):
    """
    잘못 저장된 voucher ID를 올바른 {sq_acttax2}_{company} 형식으로 변경
    기존 데이터는 보존됨
    """
    result = await voucher_service.migrate_voucher_ids()
    return {"message": "Voucher ID migration completed", "migrated_count": result}


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
    items_per_page: int = 2000,
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
