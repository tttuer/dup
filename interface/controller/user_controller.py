from datetime import datetime
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from application.user_service import UserService
from common.auth import Role
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
    roles: list[Role]


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_user(
    user: CreateUserBody,
    user_service: UserService = Depends(Provide[Container.user_service]),
) -> UserResponse:
    created_user = await user_service.create_user(
        user.user_id, user.password, user.roles
    )

    return created_user


@router.post("/login")
@inject
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    access_token = await user_service.login(form_data.username, form_data.password)

    return {"access_token": access_token, "token_type": "bearer"}
