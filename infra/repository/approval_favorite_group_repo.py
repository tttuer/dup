from typing import List, Optional

from domain.approval_favorite_group import ApprovalFavoriteGroup as DomainApprovalFavoriteGroup
from domain.repository.approval_favorite_group_repo import IApprovalFavoriteGroupRepository
from infra.db_models.approval_favorite_group import ApprovalFavoriteGroup as DBApprovalFavoriteGroup
from infra.repository.base_repo import BaseRepository


class ApprovalFavoriteGroupRepository(BaseRepository[DBApprovalFavoriteGroup], IApprovalFavoriteGroupRepository):
    def __init__(self):
        super().__init__(DBApprovalFavoriteGroup)
        self.db_model = DBApprovalFavoriteGroup
        self.domain_model = DomainApprovalFavoriteGroup
    
    def _to_domain(self, db_entity: DBApprovalFavoriteGroup) -> DomainApprovalFavoriteGroup:
        """DB 모델을 도메인 모델로 변환"""
        if not db_entity:
            return None
        return DomainApprovalFavoriteGroup(**db_entity.model_dump())
    
    def _to_db(self, domain_entity: DomainApprovalFavoriteGroup) -> DBApprovalFavoriteGroup:
        """도메인 모델을 DB 모델로 변환"""
        return DBApprovalFavoriteGroup(**domain_entity.model_dump())
    
    async def find_by_id(self, group_id: str) -> Optional[DomainApprovalFavoriteGroup]:
        db_group = await self.db_model.get(group_id)
        return self._to_domain(db_group) if db_group else None
    
    async def find_by_user_id(self, user_id: str) -> List[DomainApprovalFavoriteGroup]:
        db_groups = await self.db_model.find(
            self.db_model.user_id == user_id
        ).to_list()
        return [self._to_domain(group) for group in db_groups]
    
    async def find_by_user_and_name(self, user_id: str, name: str) -> Optional[DomainApprovalFavoriteGroup]:
        db_group = await self.db_model.find_one(
            self.db_model.user_id == user_id,
            self.db_model.name == name
        )
        return self._to_domain(db_group) if db_group else None
    
    async def save(self, group: DomainApprovalFavoriteGroup) -> DomainApprovalFavoriteGroup:
        db_group = self._to_db(group)
        existing = await self.db_model.get(group.id)
        if existing:
            # 업데이트
            await existing.set(db_group.model_dump())
            return self._to_domain(existing)
        else:
            # 생성
            saved_group = await db_group.insert()
            return self._to_domain(saved_group)
    
    async def delete_by_id(self, group_id: str) -> None:
        db_group = await self.db_model.get(group_id)
        if db_group:
            await db_group.delete()