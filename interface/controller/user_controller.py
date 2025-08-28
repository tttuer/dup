from datetime import datetime
from typing import Annotated, Optional

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Request, Response, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from utils.settings import settings

from application.user_service import UserService
from common.auth import (
    CurrentUser,
    Role,
    ApprovalStatus,
    get_current_user,
    clear_refresh_token_cookie,
    get_user_id_from_refresh_token,
    create_access_token,
)
from containers import Container
from domain.responses.user_response import UserResponse
from common.exceptions import PermissionError

router = APIRouter(prefix="/users", tags=["users"])




class CreateUserBody(BaseModel):
    user_id: str
    name: Optional[str] = None
    password: str
    roles: list[Role]

class SignupUserBody(BaseModel):
    user_id: str
    name: Optional[str] = None
    password: str

class UpdateUserBody(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    roles: Optional[list[Role]] = None

class ApproveUserBody(BaseModel):
    approval_status: ApprovalStatus
    roles: list[Role]


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_user(
    user: CreateUserBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> UserResponse:
    if current_user.id != settings.wehago_id:
        raise PermissionError("Only the admin can create users.")
    
    created_user = await user_service.create_user(
        user_id=user.user_id,
        name=user.name,
        password=user.password,
        roles=user.roles,
    )

    return created_user


@router.post("/signup", status_code=status.HTTP_201_CREATED)
@inject
async def signup_user(
    user: SignupUserBody,
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> UserResponse:
    created_user = await user_service.signup_user(
        user_id=user.user_id,
        name=user.name,
        password=user.password,
    )

    return created_user


@router.post("/login")
@inject
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    access_token, refresh_token = await user_service.login(
        form_data.username, form_data.password
    )

    # Refresh Token을 쿠키에 설정
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # 로컬 테스트 중이면 False
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
@inject
async def get_current_user_info(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> UserResponse:
    """현재 접속한 사용자 정보 조회"""
    user = await user_service.find_by_user_id(current_user.id)
    return user


@router.get("")
@inject
async def find(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> list[UserResponse]:

    users = await user_service.find()

    return users


@router.post("/refresh")
@inject
async def refresh_token(
    request: Request,
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    user_id = get_user_id_from_refresh_token(request)
    user = await user_service.find_by_user_id(user_id)
    roles = user.roles if user else []

    new_access_token = create_access_token(
        payload={"user_id": user_id},
        roles=roles,
    )

    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout")
def logout(response: Response):

    clear_refresh_token_cookie(response)
    return {"message": "Logged out"}

@router.patch("/{user_id}")
@inject
async def update_user(
    user_id: str,
    user: UpdateUserBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> UserResponse:
    updated_user = await user_service.update_user(
        user_id=user_id,
        name=user.name,
        password=user.password,
        roles=user.roles,
    )

    return updated_user


@router.patch("/{user_id}/approval")
@inject
async def approve_user(
    user_id: str,
    approval: ApproveUserBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> UserResponse:
    if Role.ADMIN not in current_user.roles:
        raise PermissionError("Only admin can approve users")
    
    approved_user = await user_service.approve_user(
        user_id=user_id,
        approval_status=approval.approval_status,
        roles=approval.roles,
    )

    return approved_user


@router.get("/pending")
@inject
async def get_pending_users(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> list[UserResponse]:
    if Role.ADMIN not in current_user.roles:
        raise PermissionError("Only admin can view pending users")
    
    pending_users = await user_service.find_pending_users()
    return pending_users


@router.get("/search")
@inject
async def search_users_by_name(
    name: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> list[UserResponse]:
    """이름으로 사용자 검색 (결재자 선택용)"""
    users = await user_service.search_users_by_name(name)
    return users