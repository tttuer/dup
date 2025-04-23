from dataclasses import dataclass
from datetime import timedelta, datetime, UTC
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from starlette import status

SECRET_KEY = "pyeongtaek_baeksung_secret_key"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")


class Role(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"


@dataclass
class CurrentUser:
    id: str
    role: Role


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    payload = decode_token(token)

    user_id = payload.get("user_id")
    role = payload.get("role")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return CurrentUser(id=user_id, role=role)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


def create_access_token(
    payload: dict,
    role: Role,
    expires_delta: timedelta = timedelta(hours=6),
):
    expire = datetime.now(UTC) + expires_delta
    payload.update({"exp": expire, "role": role})

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt
