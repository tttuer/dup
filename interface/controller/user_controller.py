from datetime import datetime
from typing import Annotated, Optional

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, Request, Response, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from utils.settings import settings

from application.user_service import UserService
from common.auth import (
    CurrentUser,
    Role,
    get_current_user,
    clear_refresh_token_cookie,
    get_user_id_from_refresh_token,
    create_access_token,
)
from containers import Container
from domain.responses.user_response import UserResponse

router = APIRouter(prefix="/users", tags=["users"])




class CreateUserBody(BaseModel):
    user_id: str
    name: Optional[str] = None
    password: str
    roles: list[Role]

class UpdateUserBody(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    roles: Optional[list[Role]] = None


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_user(
    user: CreateUserBody,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> UserResponse:
    if current_user.id != settings.wehago_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the admin can create users.",
        )
    
    created_user = await user_service.create_user(
        user_id=user.user_id,
        name=user.name,
        password=user.password,
        roles=user.roles,
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