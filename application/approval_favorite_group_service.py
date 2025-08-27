from utils.time import get_utc_now_naive
from typing import List
from dependency_injector.wiring import inject
from fastapi import HTTPException
from ulid import ULID

from application.base_service import BaseService
from domain.repository.approval_favorite_group_repo import IApprovalFavoriteGroupRepository
from domain.repository.user_repo import IUserRepository
from domain.approval_favorite_group import ApprovalFavoriteGroup


class ApprovalFavoriteGroupService(BaseService[ApprovalFavoriteGroup]):
    @inject
    def __init__(
        self,
        favorite_group_repo: IApprovalFavoriteGroupRepository,
        user_repo: IUserRepository,
    ):
        super().__init__(user_repo)
        self.favorite_group_repo = favorite_group_repo
        self.ulid = ULID()

    async def create_favorite_group(
        self,
        user_id: str,
        name: str,
        approver_ids: List[str],
    ) -> ApprovalFavoriteGroup:
        # 중복 이름 확인
        existing_group = await self.favorite_group_repo.find_by_user_and_name(user_id, name)
        if existing_group:
            raise HTTPException(status_code=400, detail="Group with this name already exists")

        # 결재자들 유효성 확인 및 이름 가져오기
        users_dict = await self.validate_users_exist(approver_ids)
        approver_names = [users_dict[approver_id].name for approver_id in approver_ids]

        group = ApprovalFavoriteGroup(
            id=self.ulid.generate(),
            user_id=user_id,
            name=name,
            approver_ids=approver_ids,
            approver_names=approver_names,
            created_at=get_utc_now_naive(),
            updated_at=get_utc_now_naive(),
        )
        print("Debug - group to save:", group)

        return await self.favorite_group_repo.save(group)

    async def get_user_favorite_groups(self, user_id: str) -> List[ApprovalFavoriteGroup]:
        return await self.favorite_group_repo.find_by_user_id(user_id)

    async def update_favorite_group(
        self,
        group_id: str,
        user_id: str,
        name: str = None,
        approver_ids: List[str] = None,
    ) -> ApprovalFavoriteGroup:
        group = await self.favorite_group_repo.find_by_id(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Favorite group not found")
        
        if group.user_id != user_id:
            raise HTTPException(status_code=403, detail="No permission to modify this group")

        # 이름 변경 시 중복 확인
        if name and name != group.name:
            existing_group = await self.favorite_group_repo.find_by_user_and_name(user_id, name)
            if existing_group:
                raise HTTPException(status_code=400, detail="Group with this name already exists")
            group.name = name

        # 결재자 목록 변경 시 유효성 확인
        if approver_ids is not None:
            users_dict = await self.validate_users_exist(approver_ids)
            approver_names = [users_dict[approver_id].name for approver_id in approver_ids]
            
            group.approver_ids = approver_ids
            group.approver_names = approver_names

        group.updated_at = get_utc_now_naive()
        print("Debug - group to save:", group)
        return await self.favorite_group_repo.save(group)

    async def delete_favorite_group(self, group_id: str, user_id: str) -> None:
        group = await self.favorite_group_repo.find_by_id(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Favorite group not found")
        
        if group.user_id != user_id:
            raise HTTPException(status_code=403, detail="No permission to delete this group")

        await self.favorite_group_repo.delete_by_id(group_id)

    async def get_favorite_group_by_id(self, group_id: str, user_id: str) -> ApprovalFavoriteGroup:
        group = await self.favorite_group_repo.find_by_id(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Favorite group not found")
        
        if group.user_id != user_id:
            raise HTTPException(status_code=403, detail="No permission to access this group")

        return group