from abc import ABCMeta, abstractmethod
from typing import List, Optional
from domain.user import User


class IUserRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_user_id(self, user_id: str) -> Optional[User]:
        raise NotImplementedError
    
    @abstractmethod
    async def find(self) -> List[User]:
        raise NotImplementedError
    
    @abstractmethod
    async def update(self, user: User) -> User:
        raise NotImplementedError
