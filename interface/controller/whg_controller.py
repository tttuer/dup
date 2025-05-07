from fastapi import APIRouter, Depends
from dependency_injector.wiring import inject, Provide
from common.auth import CurrentUser
from containers import Container
from typing import Annotated
from common.auth import get_current_user
from application.voucher_service import VoucherService
from domain.voucher import Company

router = APIRouter(prefix="/whg", tags=["whg"])


@router.get("/sync")
@inject
async def sync_whg(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    voucher_service: VoucherService = Depends(Provide[Container.voucher_service]),
    company: Company = Company.BAEKSUNG,
):
    await voucher_service.save_vouchers(company=company)

    return {"message": "Sync completed successfully"}
