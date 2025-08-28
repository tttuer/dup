from typing import List, Optional

from domain.approval_favorite_group import (
    ApprovalFavoriteGroup as DomainApprovalFavoriteGroup,
)
from domain.repository.approval_favorite_group_repo import (
    IApprovalFavoriteGroupRepository,
)
from infra.db_models.approval_favorite_group import (
    ApprovalFavoriteGroup as ApprovalFavoriteGroup,
)
from infra.repository.base_repo import BaseRepository


class ApprovalFavoriteGroupRepository(
    BaseRepository[ApprovalFavoriteGroup], IApprovalFavoriteGroupRepository
):
    def __init__(self):
        super().__init__(ApprovalFavoriteGroup)
        self.db_model = ApprovalFavoriteGroup
        self.domain_model = DomainApprovalFavoriteGroup

    def _to_domain(
        self, db_entity: ApprovalFavoriteGroup
    ) -> DomainApprovalFavoriteGroup:
        """DB 모델을 도메인 모델로 변환"""
        if not db_entity:
            return None
        return DomainApprovalFavoriteGroup(**db_entity.model_dump())

    def _to_db(
        self, domain_entity: DomainApprovalFavoriteGroup
    ) -> ApprovalFavoriteGroup:
        """도메인 모델을 DB 모델로 변환"""
        return ApprovalFavoriteGroup(**domain_entity.model_dump())

    async def find_by_id(self, group_id: str) -> Optional[ApprovalFavoriteGroup]:
        return await self.db_model.get(group_id)

    async def find_by_user_id(self, user_id: str) -> List[ApprovalFavoriteGroup]:
        return await self.db_model.find(self.db_model.user_id == user_id).to_list()

    async def find_by_user_and_name(
        self, user_id: str, name: str
    ) -> Optional[ApprovalFavoriteGroup]:
        return await self.db_model.find_one(
            self.db_model.user_id == user_id, self.db_model.name == name
        )

    async def save(self, group: DomainApprovalFavoriteGroup) -> ApprovalFavoriteGroup:
        new_group = ApprovalFavoriteGroup(
            id=group.id,
            user_id=group.user_id,
            name=group.name,
            approver_ids=group.approver_ids,
            approver_names=group.approver_names,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
        existing = await self.db_model.get(group.id)
        if existing:
            # 업데이트
            await existing.set(new_group.model_dump())
            return existing
        else:
            # 생성
            return await new_group.insert()

    async def delete_by_id(self, group_id: str) -> None:
        db_group = await self.db_model.get(group_id)
        if db_group:
            await db_group.delete()
