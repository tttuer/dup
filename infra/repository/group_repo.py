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

        return GroupVo(**saved_group.model_dump())

    async def find_by_id(self, id: str) -> GroupVo:
        group = await super().find_by_id_or_raise(id, "Group")
        return GroupVo(**group.model_dump())

    async def find(self, *filters: Any) -> list[GroupVo]:
        groups = await Group.find(*filters).to_list()

        if not groups:
            return []

        return [GroupVo(**group.model_dump()) for group in groups]

    async def find_by_name_and_company(self, name: str, company: str) -> GroupVo:
        group = await Group.find_one(Group.name == name, Group.company == company)

        if not group:
            return None
        return GroupVo(**group.model_dump())

    async def delete(self, id: str, session=None):
        group = await super().find_by_id_or_raise(id, "Group")
        await group.delete(session=session)

    async def update(self, update_group: GroupVo):
        db_group = await super().find_by_id_or_raise(update_group.id, "Group")

        update_data = asdict(update_group)
        update_data.pop("id", None)

        for field, value in update_data.items():
            if value is not None:
                setattr(db_group, field, value)

        updated_group = await super().update(db_group)
        return GroupVo(**updated_group.model_dump())
