from abc import ABC, abstractmethod
from typing import List, Optional

from domain.approval_favorite_group import ApprovalFavoriteGroup


class IApprovalFavoriteGroupRepository(ABC):
    @abstractmethod
    async def find_by_id(self, group_id: str) -> Optional[ApprovalFavoriteGroup]:
        pass
    
    @abstractmethod
    async def find_by_user_id(self, user_id: str) -> List[ApprovalFavoriteGroup]:
        pass
    
    @abstractmethod
    async def save(self, group: ApprovalFavoriteGroup) -> ApprovalFavoriteGroup:
        pass
    
    @abstractmethod
    async def delete_by_id(self, group_id: str) -> None:
        pass
    
    @abstractmethod
    async def find_by_user_and_name(self, user_id: str, name: str) -> Optional[ApprovalFavoriteGroup]:
        pass