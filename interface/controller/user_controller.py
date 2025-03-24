from datetime import datetime
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from starlette.responses import RedirectResponse

from application.user_service import UserService
from containers import Container

router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class CreateUserBody(BaseModel):
    user_id: str
    password: str


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_user(
    user: CreateUserBody,
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> UserResponse:
    created_user = await user_service.create_user(user.user_id, user.password)

    return created_user


@router.post("/login")
@inject
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    access_token = await user_service.login(form_data.username, form_data.password)

    response = RedirectResponse(url="/lists", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,  # <-- XSS 방어
        secure=False,  # HTTPS에서 True (개발환경이면 False도 OK)
        samesite="lax",  # or "strict"
        max_age=60 * 60 * 8,  # 8시간 유지
    )

    return response
