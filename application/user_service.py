from datetime import datetime
from typing import Optional

from dependency_injector.wiring import inject
from fastapi import HTTPException
from starlette import status
from ulid import ULID

from application.base_service import BaseService
from common.auth import create_access_token, create_refresh_token, Role
from domain.repository.user_repo import IUserRepository
from domain.user import User
from domain.responses.user_response import UserResponse
from utils.crypto import Crypto


class UserService(BaseService[User]):
    @inject
    def __init__(self, user_repo: IUserRepository):
        super().__init__(user_repo)
        self.ulid = ULID()
        self.crypto = Crypto()

    async def create_user(self, user_id: str, name: Optional[str], password: str, roles: list[Role]) -> User:
        _user = None

        try:
            _user = await self.user_repo.find_by_user_id(user_id)
        except HTTPException as e:
            if e.status_code != 422 and e.status_code != 404:
                raise e

        if _user:
            raise HTTPException(
                status_code=409,
                detail="User already exists",
            )

        now = datetime.now()
        user: User = User(
            id=self.ulid.generate(),
            name=name,
            user_id=user_id,
            password=self.crypto.encrypt(password),
            created_at=now,
            updated_at=now,
            roles=roles,
        )

        await self.user_repo.save(user)

        return user

    async def login(self, user_id: str, password: str):
        user_doc = await self.user_repo.find_by_user_id(user_id)

        if not user_doc or not self.crypto.verify(password, user_doc.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = await self.get_access_token(user_id, user_doc.roles)
        refresh_token = await self.get_refresh_token(user_id)

        return access_token, refresh_token

    async def get_access_token(self, user_id: str, roles: list[Role]):
        return create_access_token(
            payload={"user_id": user_id},
            roles=roles,
        )

    async def get_refresh_token(self, user_id: str) -> str:
        return create_refresh_token(
            payload={"user_id": user_id} # 만료기간 설정
        )

    async def find(self):
        user_docs = await self.user_repo.find()

        return [UserResponse.from_document(user) for user in user_docs]
    
    async def find_by_user_id(self, user_id: str) -> UserResponse:
        user_doc = await self.validate_user_exists(user_id)
        return UserResponse.from_document(user_doc)
    
    async def update_user(
        self,
        user_id: str,
        name: Optional[str] = None,
        password: Optional[str] = None,
        roles: Optional[list[Role]] = None,
    ) -> UserResponse:
        user_doc = await self.validate_user_exists(user_id)

        if password:
            user_doc.password = self.crypto.encrypt(password)

        if name is not None:
            user_doc.name = name

        if roles is not None:
            user_doc.roles = roles

        user_doc.updated_at = datetime.now()
        updated_user_doc = await user_doc.save()

        return UserResponse.from_document(updated_user_doc)
