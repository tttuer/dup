from dependency_injector.wiring import inject

from domain.group import Group
from domain.file import Company
from domain.repository.group_repo import IGroupRepository


class GroupService:
    @inject
    def __init__(self, group_repo: IGroupRepository):
        self.group_repo = group_repo

    async def save(
        self,
        name: str,
        company: Company,
    ):
        group = Group(
            name=name,
            company=company,
        )
        await self.group_repo.save(group)

        return group

    async def find_by_id(self, id: str):
        group = await self.group_repo.find_by_id(id)

        return group

    async def find_by_company(self, company: Company):
        groups = await self.group_repo.find_by_company(company)

        return groups

    async def delete(self, id: str):
        await self.group_repo.delete(id)

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
