from fastapi import APIRouter, Depends
from dependency_injector.wiring import inject, Provide
from common.auth import CurrentUser
from containers import Container
from utils.whg import Whg
from typing import Annotated
from common.auth import get_current_user

router = APIRouter(prefix="/whg", tags=["whg"])


@router.get("/sync")
@inject
async def sync_whg(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    whg: Whg = Depends(Provide[Container.whg]),
):
    await whg.crawl_whg()
