from typing import Annotated, Optional

from dependency_injector.wiring import inject, Provide
from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Depends,
    Form,
)
from pydantic import BaseModel

from application.group_service import GroupService
from common.auth import CurrentUser, Role
from common.auth import get_current_user
from containers import Container
from domain.file import Company
from domain.responses.group_response import GroupResponse

router = APIRouter(prefix="/groups", tags=["groups"])


class CreateGroupBody(BaseModel):
    name: str
    company: Company




class GroupGrantBody(BaseModel):
    auth_users: list[str] = []


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_group(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    group_body: CreateGroupBody,
    group_service: GroupService = Depends(Provide[Container.group_service]),
) -> GroupResponse:

    group = await group_service.save(
        name=group_body.name,
        company=group_body.company,
        user_id=current_user.id,
        roles=current_user.roles,
    )
    return group


@router.get("/{id}")
@inject
async def find(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    id: str,
    group_service: GroupService = Depends(Provide[Container.group_service]),
) -> GroupResponse:

    return await group_service.find_by_id(id)


@router.get("")
@inject
async def find_by_company(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    company: Optional[Company] = Company.BAEKSUNG,
    group_service: GroupService = Depends(Provide[Container.group_service]),
) -> list[GroupResponse]:
    return await group_service.find(
        id=current_user.id,
        roles=current_user.roles,
        company=company,
    )


@router.delete("/{id}")
@inject
async def delete(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    id: str,
    group_service: GroupService = Depends(Provide[Container.group_service]),
):
    await group_service.delete(id=id, current_user_id=current_user.id, roles=current_user.roles)


@router.put("/{id}")
@inject
async def update_group(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    id: str,
    name: str = Form(...),
    group_service: GroupService = Depends(Provide[Container.group_service]),
) -> GroupResponse:

    group = await group_service.update(
        id=id,
        name=name,
    )
    return group


@router.patch("/{id}")
@inject
async def grant_group(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    id: str,
    group_body: GroupGrantBody,
    group_service: GroupService = Depends(Provide[Container.group_service]),
) -> GroupResponse:
    group = await group_service.grant_with_permission_check(
        id=id,
        auth_users=group_body.auth_users,
        current_user_id=current_user.id,
        current_user_roles=current_user.roles,
    )
    return group
