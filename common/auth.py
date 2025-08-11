from dataclasses import dataclass
from datetime import timedelta, datetime, UTC
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from utils.settings import settings
from common.exceptions import AuthenticationError, PermissionError

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")


class Role(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"
    VOUCHER = "VOUCHER"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class CurrentUser:
    id: str
    roles: list[Role]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    payload = decode_token(token)

    user_id = payload.get("user_id")
    roles = payload.get("roles", [])

    if not user_id:
        raise PermissionError("토큰에서 사용자 ID를 찾을 수 없습니다")

    return CurrentUser(id=user_id, roles=[Role(r) for r in roles])


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise AuthenticationError("토큰 검증에 실패했습니다")


def create_access_token(
    payload: dict,
    roles: list[Role],
    expires_delta: timedelta = timedelta(hours=3),
):
    expire = datetime.now(UTC) + expires_delta
    payload.update({"exp": expire, "roles": roles})

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def create_refresh_token(
    payload: dict, expires_delta: timedelta = timedelta(hours=12)
) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(UTC) + expires_delta
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def get_user_id_from_refresh_token(request: Request) -> str:
    refresh_token = request.cookies.get("refresh_token")
    print(f"Refresh token from cookies: {refresh_token}")

    if not refresh_token:
        print("Refresh token not found in cookies")
        raise AuthenticationError("리프레시 토큰이 없습니다")

    try:
        payload = decode_token(refresh_token)
    except JWTError:
        print("Invalid or expired refresh token")
        raise AuthenticationError("유효하지 않거나 만료된 리프레시 토큰입니다")

    user_id = payload.get("user_id")
    if not user_id:
        print("Invalid token payload: user_id not found")
        raise AuthenticationError("토큰 페이로드가 유효하지 않습니다")

    return user_id


def clear_refresh_token_cookie(response: Response):
    response.delete_cookie(
        key="refresh_token",
        path="/",
        secure=True,  # set_cookie 쪽과 동일하게
        httponly=True,  # set_cookie 쪽과 동일하게
        samesite="lax",  # set_cookie 쪽과 동일하게
    )
