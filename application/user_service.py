from datetime import datetime

from dependency_injector.wiring import inject
from fastapi import HTTPException
from starlette import status
from ulid import ULID

from common.auth import create_access_token, create_refresh_token, Role
from domain.repository.user_repo import IUserRepository
from domain.user import User
from utils.crypto import Crypto


class UserService:
    @inject
    def __init__(self, user_repo: IUserRepository):
        self.user_repo = user_repo
        self.ulid = ULID()
        self.crypto = Crypto()

    async def create_user(self, user_id: str, password: str, roles: list[Role]) -> User:
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
            user_id=user_id,
            password=self.crypto.encrypt(password),
            created_at=now,
            updated_at=now,
            roles=roles,
        )

        await self.user_repo.save(user)

        return user

    async def login(self, user_id: str, password: str):
        user = await self.user_repo.find_by_user_id(user_id)

        if not self.crypto.verify(password, user.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        access_token = await self.get_access_token(user_id, user.roles)
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
        user = await self.user_repo.find()

        return user
    
    async def find_by_user_id(self, user_id: str) -> User:
        user = await self.user_repo.find_by_user_id(user_id)

        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User not found: {user_id}",
            )

        return user
