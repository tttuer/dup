from datetime import datetime

from dependency_injector.wiring import inject
from fastapi import HTTPException
from starlette import status
from ulid import ULID

from common.auth import create_access_token, Role
from domain.repository.user_repo import IUserRepository
from domain.user import User
from utils.crypto import Crypto


class UserService:
    @inject
    def __init__(self, user_repo: IUserRepository):
        self.user_repo = user_repo
        self.ulid = ULID()
        self.crypto = Crypto()

    async def create_user(self, user_id: str, password: str, role: Role) -> User:
        _user = None

        try:
            _user = await self.user_repo.find_by_user_id(user_id)
        except HTTPException as e:
            if e.status_code != 422 and e.status_code != 404:
                raise e

        if _user:
            raise HTTPException(
                status_code=422,
            )

        now = datetime.now()
        user: User = User(
            id=self.ulid.generate(),
            user_id=user_id,
            password=self.crypto.encrypt(password),
            created_at=now,
            updated_at=now,
            role=role,
        )

        await self.user_repo.save(user)

        return user

    async def login(self, user_id: str, password: str):
        user = await self.user_repo.find_by_user_id(user_id)

        if not self.crypto.verify(password, user.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        return await self.get_access_token(user_id, user.role)

    async def get_access_token(self, user_id: str, role: Role):
        return create_access_token(
            payload={"user_id": user_id},
            role=role,
        )
