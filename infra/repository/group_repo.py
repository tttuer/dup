from dataclasses import asdict
from typing import Any

from fastapi import HTTPException

from domain.group import Group as GroupVo
from domain.repository.group_repo import IGroupRepository
from infra.db_models.group import Group
from infra.repository.base_repo import BaseRepository


class GroupRepository(BaseRepository[Group], IGroupRepository):
    def __init__(self):
        super().__init__(Group)
    async def save(self, group: GroupVo):
        new_group = Group(
            id=group.id,
            name=group.name,
            company=group.company,
            auth_users=group.auth_users or [],
        )

        saved_group = await Group.insert(new_group)

        return saved_group

    async def find_by_id(self, id: str) -> Group:
        group = await Group.get(id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        return group

    async def find(self, *filters: Any) -> list[Group]:
        groups = await Group.find(*filters).to_list()

        if not groups:
            return []

        return groups

    async def find_by_name_and_company(self, name: str, company: str) -> Group:
        group = await Group.find_one(Group.name == name, Group.company == company)

        if not group:
            return None
        return group

    async def delete(self, id: str, session=None):
        group = await Group.get(id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        await group.delete(session=session)

    async def update(self, update_group: GroupVo):
        db_group = await Group.get(update_group.id)
        if not db_group:
            raise HTTPException(status_code=404, detail="Group not found")

        update_data = asdict(update_group)
        update_data.pop("id", None)

        for field, value in update_data.items():
            if value is not None:
                setattr(db_group, field, value)

        updated_group = await db_group.save()
        return updated_group
