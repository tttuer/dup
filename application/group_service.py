from dependency_injector.wiring import inject
from fastapi import HTTPException

from domain.group import Group
from domain.file import Company
from domain.repository.file_repo import IFileRepository
from domain.repository.group_repo import IGroupRepository
from ulid import ULID
from common.db import client



class GroupService:
    @inject
    def __init__(self, group_repo: IGroupRepository, file_repo: IFileRepository):
        self.group_repo = group_repo
        self.file_repo = file_repo
        self.ulid = ULID()

    async def save(
        self,
        name: str,
        company: Company,
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
        )
        saved_group = await self.group_repo.save(group)

        return saved_group

    async def find_by_id(self, id: str):
        group = await self.group_repo.find_by_id(id)

        return group

    async def find_by_company(self, company: Company):
        groups = await self.group_repo.find_by_company(company)

        return groups

    async def delete(self, id: str):
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
