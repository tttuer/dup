from abc import ABCMeta, abstractmethod
from typing import List, Optional
from domain.user import User as UserVo
from infra.db_models.user import User
from common.auth import ApprovalStatus


class IUserRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, user: UserVo) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_user_id(self, user_id: str) -> Optional[User]:
        raise NotImplementedError
    
    @abstractmethod
    async def find(self) -> List[User]:
        raise NotImplementedError
    
    @abstractmethod
    async def update(self, user: UserVo) -> User:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_approval_status(self, approval_status: ApprovalStatus) -> List[User]:
        raise NotImplementedError
