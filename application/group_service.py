from dependency_injector.wiring import inject
from fastapi import HTTPException

from application.base_service import BaseService
from common.auth import CurrentUser, Role
from domain.group import Group
from domain.file import Company
from domain.repository.file_repo import IFileRepository
from domain.repository.group_repo import IGroupRepository
from domain.repository.user_repo import IUserRepository
from ulid import ULID
from infra.db_models.group import Group as GroupDocument
from common.db import client
from beanie.operators import And, In


class GroupService(BaseService[Group]):
    @inject
    def __init__(self, group_repo: IGroupRepository, file_repo: IFileRepository, user_repo: IUserRepository):
        super().__init__(user_repo)
        self.group_repo = group_repo
        self.file_repo = file_repo
        self.ulid = ULID()

    async def save(
        self,
        name: str,
        company: Company,
        user_id: str,
        roles: list[Role],
    ):
        db_group = await self.group_repo.find_by_name_and_company(name, company)
        if db_group:
            raise HTTPException(
                status_code=409,
                detail="Group with this name already exists",
            )

        group = Group(
            id=self.ulid.generate(),
            name=name,
            company=company,
            auth_users=[user_id] if Role.ADMIN not in roles else [],
        )
        saved_group = await self.group_repo.save(group)

        return saved_group

    async def find_by_id(self, id: str):
        group = await self.group_repo.find_by_id(id)

        return group

    async def find(self, company: Company, id: str, roles: list[Role]):
        filters = []
        if Role.ADMIN not in roles:
            filters.append(In(GroupDocument.auth_users, [id]))

        filters.append(GroupDocument.company == company)

        groups = await self.group_repo.find(And(*filters))

        return groups

    async def delete(self, id: str, current_user_id: str, roles: list[Role]):
        group = await self.group_repo.find_by_id(id)

        if not group:
            raise HTTPException(
                status_code=404,
                detail="Group not found",
            )
        
        await self._validate_group_permission(group, current_user_id, roles)

        async with await client.start_session() as session:
            async with session.start_transaction():
                # Delete all files associated with the group
                await self.file_repo.delete_by_group_id(id, session=session)
                await self.group_repo.delete(id, session=session)

                # Delete the group itself

    async def update(
        self,
        id: str,
        name: str,
    ):
        
        group: Group = Group(
            id=id,
            name=name,
        )

        update_group = await self.group_repo.update(group)

        return update_group

    async def grant(
        self,
        id: str,
        auth_users: list[str],
    ):
        group = await self.group_repo.find_by_id(id)

        if not group:
            raise HTTPException(
                status_code=404,
                detail="Group not found",
            )

        group.auth_users = auth_users
        updated_group = await self.group_repo.update(group)

        return updated_group
    
    async def _validate_group_permission(self, group: Group, user_id: str, roles: list[Role]):
        """Validate that user has permission to access the group."""
        if user_id not in group.auth_users and Role.ADMIN not in roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this group",
            )
    
    async def grant_with_permission_check(
        self,
        id: str,
        auth_users: list[str],
        current_user_id: str,
        current_user_roles: list[Role],
    ):
        """Grant access to group with proper permission validation."""
        group = await self.group_repo.find_by_id(id)
        
        if not group:
            raise HTTPException(
                status_code=404,
                detail="Group not found",
            )
        
        await self._validate_group_permission(group, current_user_id, current_user_roles)
        
        group.auth_users = auth_users
        updated_group = await self.group_repo.update(group)
        
        return updated_group