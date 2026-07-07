from datetime import datetime, timezone
from typing import Optional, List, Dict

import json
from dependency_injector.wiring import inject
from common.exceptions import ConflictError, AuthenticationError, PermissionError, InternalServerError, NotFoundError
from ulid import ULID
from redis.asyncio import Redis

from application.base_service import BaseService
from common.auth import create_access_token, create_refresh_token, Role, ApprovalStatus
from domain.repository.user_repo import IUserRepository
from domain.user import User
from domain.responses.user_response import UserResponse
from utils.crypto import Crypto
from utils.time import get_utc_now_naive
from utils.slack import send_signup_notification


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

        now = get_utc_now_naive()
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
        now = get_utc_now_naive()
        same_user_id_docs = await self.user_repo.find_all_by_user_id(user_id)
        approved_user = next(
            (user for user in same_user_id_docs if user.approval_status == ApprovalStatus.APPROVED),
            None,
        )

        if approved_user:
            raise ConflictError("이미 가입 승인된 아이디입니다")

        reusable_request = self._get_latest_user_doc(same_user_id_docs)
        if reusable_request:
            reusable_request.name = name
            reusable_request.password = self.crypto.encrypt(password)
            reusable_request.roles = []
            reusable_request.approval_status = ApprovalStatus.PENDING
            reusable_request.updated_at = now
            updated_user = await reusable_request.save()
            await self._broadcast_pending_count()
            return updated_user

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

        # 슬랙 알림 전송
        try:
            await send_signup_notification(user_id, name)
        except Exception as e:
            # 슬랙 알림 실패해도 회원가입은 성공 처리
            pass

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

        user_doc.updated_at = get_utc_now_naive()
        updated_user_doc = await user_doc.save()

        return UserResponse.from_document(updated_user_doc)

    async def delete_user(self, user_id: str, requester_user_id: Optional[str] = None) -> None:
        user_doc = await self._find_user_by_id_or_user_id(user_id)
        if requester_user_id and user_doc.user_id == requester_user_id:
            raise PermissionError("Cannot delete your own account")

        was_pending = user_doc.approval_status == ApprovalStatus.PENDING

        await user_doc.delete()

        if was_pending:
            await self._broadcast_pending_count()

    async def approve_user(
        self,
        user_id: str,
        approval_status: ApprovalStatus,
        roles: list[Role],
    ) -> UserResponse:
        user_doc = await self._find_user_by_id_or_user_id(user_id)

        if approval_status == ApprovalStatus.REJECTED:
            await user_doc.delete()
            # 거절 시 pending 수 업데이트 브로드캐스트
            await self._broadcast_pending_count()
            return UserResponse.from_document(user_doc)

        if approval_status == ApprovalStatus.APPROVED:
            await self._validate_latest_pending_request(user_doc)
            await self._validate_no_approved_duplicate(user_doc)

        user_doc.approval_status = approval_status
        user_doc.roles = roles
        user_doc.updated_at = get_utc_now_naive()
        
        updated_user_doc = await user_doc.save()

        # 승인 시 pending 수 업데이트 브로드캐스트
        await self._broadcast_pending_count()

        return UserResponse.from_document(updated_user_doc)

    async def find_pending_users(self) -> list[UserResponse]:
        pending_users = await self.user_repo.find_by_approval_status(ApprovalStatus.PENDING)
        latest_pending_by_user_id = {}
        for user in pending_users:
            current = latest_pending_by_user_id.get(user.user_id)
            if not current or self._get_user_doc_timestamp(user) > self._get_user_doc_timestamp(current):
                latest_pending_by_user_id[user.user_id] = user

        return [
            UserResponse.from_document(user)
            for user in sorted(
                latest_pending_by_user_id.values(),
                key=self._get_user_doc_timestamp,
                reverse=True,
            )
        ]

    async def _find_user_by_id_or_user_id(self, user_id: str):
        user_doc = await self.user_repo.find_by_id(user_id)
        if user_doc:
            return user_doc

        user_doc = await self.user_repo.find_by_user_id(user_id)
        if user_doc:
            return user_doc

        raise NotFoundError(f"User not found: {user_id}")

    async def _validate_no_approved_duplicate(self, user_doc) -> None:
        same_user_id_docs = await self.user_repo.find_all_by_user_id(user_doc.user_id)
        has_approved_duplicate = any(
            doc.id != user_doc.id and doc.approval_status == ApprovalStatus.APPROVED
            for doc in same_user_id_docs
        )

        if has_approved_duplicate:
            raise ConflictError("이미 승인된 동일 아이디 회원이 있습니다")

    async def _validate_latest_pending_request(self, user_doc) -> None:
        if user_doc.approval_status != ApprovalStatus.PENDING:
            return

        pending_docs = [
            doc
            for doc in await self.user_repo.find_all_by_user_id(user_doc.user_id)
            if doc.approval_status == ApprovalStatus.PENDING
        ]
        latest_pending_doc = self._get_latest_user_doc(pending_docs)

        if latest_pending_doc and latest_pending_doc.id != user_doc.id:
            raise ConflictError("최신 회원가입 요청만 승인할 수 있습니다")

    def _get_latest_user_doc(self, user_docs):
        if not user_docs:
            return None

        return max(user_docs, key=self._get_user_doc_timestamp)

    def _get_user_doc_timestamp(self, user_doc):
        return user_doc.updated_at or user_doc.created_at

    async def get_pending_users_count(self) -> int:
        pending_users = await self.find_pending_users()
        return len(pending_users)

    async def search_users_by_name(self, name: str) -> list[UserResponse]:
        users = await self.user_repo.search_by_name(name)
        return [UserResponse.from_document(user) for user in users]
    
    async def find_by_user_ids_optimized(self, user_ids: List[str]) -> Dict[str, UserResponse]:
        """
        여러 사용자를 효율적으로 조회 (N+1 쿼리 문제 해결)
        DB에서 일괄 조회
        """
        if not user_ids:
            return {}
        
        # DB에서 일괄 조회
        users = await self.user_repo.find_by_user_ids(user_ids)
        
        # 결과 매핑
        result = {}
        for user_doc in users:
            user_response = UserResponse.from_document(user_doc)
            result[user_doc.user_id] = user_response
        
        return result

    async def _broadcast_pending_count(self):
        try:
            pending_count = await self.get_pending_users_count()
            message = {"pending_users_count": pending_count}
            await self.redis.publish("pending_users_channel", json.dumps(message))
        except Exception as e:
            raise InternalServerError(f"대기 사용자 수 브로드캐스트 실패: {e}")
