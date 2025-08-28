from abc import ABC, abstractmethod
from typing import List, Optional

from infra.db_models.approval_favorite_group import ApprovalFavoriteGroup as DBApprovalFavoriteGroup
from domain.approval_favorite_group import ApprovalFavoriteGroup as DomainApprovalFavoriteGroup


class IApprovalFavoriteGroupRepository(ABC):
    @abstractmethod
    async def find_by_id(self, group_id: str) -> Optional[DBApprovalFavoriteGroup]:
        pass
    
    @abstractmethod
    async def find_by_user_id(self, user_id: str) -> List[DBApprovalFavoriteGroup]:
        pass
    
    @abstractmethod
    async def save(self, group: DomainApprovalFavoriteGroup) -> DBApprovalFavoriteGroup:
        pass
    
    @abstractmethod
    async def delete_by_id(self, group_id: str) -> None:
        pass
    
    @abstractmethod
    async def find_by_user_and_name(self, user_id: str, name: str) -> Optional[DBApprovalFavoriteGroup]:
        pass