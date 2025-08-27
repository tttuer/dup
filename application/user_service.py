from datetime import datetime, timezone
from typing import Optional

import json
from dependency_injector.wiring import inject
from common.exceptions import ConflictError, AuthenticationError, PermissionError
from ulid import ULID
from redis.asyncio import Redis

from application.base_service import BaseService
from common.auth import create_access_token, create_refresh_token, Role, ApprovalStatus
from domain.repository.user_repo import IUserRepository
from domain.user import User
from domain.responses.user_response import UserResponse
from utils.crypto import Crypto


class UserService(BaseService[User]):
    @inject
    def __init__(self, user_repo: IUserRepository, redis: Redis):
        super().__init__(user_repo)
        self.ulid = ULID()
        self.crypto = Crypto()
        self.redis = redis

    async def create_user(self, user_id: str, name: Optional[str], password: str, roles: list[Role]) -> User:
        _user = None

        try:
            _user = await self.user_repo.find_by_user_id(user_id)
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code not in [422, 404]:
                raise e

        if _user:
            raise ConflictError("User already exists")

        now = datetime.now(timezone.utc)
        user: User = User(
            id=self.ulid.generate(),
            name=name,
            user_id=user_id,
            password=self.crypto.encrypt(password),
            created_at=now,
            updated_at=now,
            roles=roles,
            approval_status=ApprovalStatus.APPROVED,
        )

        await self.user_repo.save(user)

        return user

    async def signup_user(self, user_id: str, name: Optional[str], password: str) -> User:
        _user = await self.user_repo.find_by_user_id(user_id)

        if _user:
            raise ConflictError("User already exists")

        now = datetime.now(timezone.utc)
        user: User = User(
            id=self.ulid.generate(),
            name=name,
            user_id=user_id,
            password=self.crypto.encrypt(password),
            created_at=now,
            updated_at=now,
            roles=[],
            approval_status=ApprovalStatus.PENDING,
        )

        await self.user_repo.save(user)

        # 회원가입 시 pending 수 업데이트 브로드캐스트
        await self._broadcast_pending_count()

        return user

    async def login(self, user_id: str, password: str):
        user_doc = await self.user_repo.find_by_user_id(user_id)

        if not user_doc or not self.crypto.verify(password, user_doc.password):
            raise AuthenticationError("Incorrect username or password")

        if user_doc.approval_status is not None and user_doc.approval_status != ApprovalStatus.APPROVED:
            raise PermissionError("Account pending approval")

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

        user_doc.updated_at = datetime.now(timezone.utc)
        updated_user_doc = await user_doc.save()

        return UserResponse.from_document(updated_user_doc)

    async def approve_user(
        self,
        user_id: str,
        approval_status: ApprovalStatus,
        roles: list[Role],
    ) -> UserResponse:
        user_doc = await self.validate_user_exists(user_id)

        if approval_status == ApprovalStatus.REJECTED:
            await user_doc.delete()
            # 거절 시 pending 수 업데이트 브로드캐스트
            await self._broadcast_pending_count()
            return UserResponse.from_document(user_doc)

        user_doc.approval_status = approval_status
        user_doc.roles = roles
        user_doc.updated_at = datetime.now(timezone.utc)
        
        updated_user_doc = await user_doc.save()

        # 승인 시 pending 수 업데이트 브로드캐스트
        await self._broadcast_pending_count()

        return UserResponse.from_document(updated_user_doc)

    async def find_pending_users(self) -> list[UserResponse]:
        pending_users = await self.user_repo.find_by_approval_status(ApprovalStatus.PENDING)
        return [UserResponse.from_document(user) for user in pending_users]

    async def get_pending_users_count(self) -> int:
        pending_users = await self.user_repo.find_by_approval_status(ApprovalStatus.PENDING)
        return len(pending_users)

    async def search_users_by_name(self, name: str) -> list[UserResponse]:
        users = await self.user_repo.search_by_name(name)
        return [UserResponse.from_document(user) for user in users]

    async def _broadcast_pending_count(self):
        try:
            pending_count = await self.get_pending_users_count()
            message = {"pending_users_count": pending_count}
            await self.redis.publish("pending_users_channel", json.dumps(message))
        except Exception as e:
            print(f"🚨 Failed to broadcast pending count: {e}")
