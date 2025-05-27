from dataclasses import asdict
from typing import Any

from fastapi import HTTPException

from domain.group import Group as GroupVo
from domain.repository.group_repo import IGroupRepository
from infra.db_models.group import Group


class GroupRepository(IGroupRepository):
    async def save(self, group: GroupVo):
        new_group = Group(
            id=group.id,
            name=group.name,
            company=group.company,
        )

        saved_group = await Group.insert(new_group)

        return GroupVo(**saved_group.model_dump())

    async def find_by_id(self, id: str) -> GroupVo:
        group = await Group.get(id)

        if not group:
            raise HTTPException(
                status_code=404,
                detail="File not found",
            )

        return GroupVo(**group.model_dump())
    
    async def find_by_company(self, company: str) -> list[GroupVo]:
        groups = await Group.find(Group.company == company).to_list()

        if not groups:
            raise HTTPException(
                status_code=404,
                detail="No groups found for the specified company",
            )

        return [GroupVo(**group.model_dump()) for group in groups]

    async def delete(self, id: str):
        group = await Group.get(id)

        if not group:
            raise HTTPException(
                status_code=404,
            )

        await group.delete()

    async def update(self, update_group: GroupVo):
        db_group = await Group.get(update_group.id)

        if not db_group:
            raise HTTPException(
                status_code=404,
                detail="File not found",
            )

        update_data = asdict(update_group)
        update_data.pop("id", None)

        for field, value in update_data.items():
            if value is not None:
                setattr(db_group, field, value)

        await db_group.save()
        return db_group
