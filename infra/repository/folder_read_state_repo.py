from beanie.operators import In

from domain.folder_read_state import FolderReadState as FolderReadStateVo
from domain.repository.folder_read_state_repo import IFolderReadStateRepository
from infra.db_models.folder_read_state import FolderReadState


class FolderReadStateRepository(IFolderReadStateRepository):
    async def find_by_user_and_group_ids(
        self,
        user_id: str,
        group_ids: list[str],
    ) -> list[FolderReadState]:
        if not group_ids:
            return []

        return await FolderReadState.find(
            FolderReadState.user_id == user_id,
            In(FolderReadState.group_id, group_ids),
        ).to_list()

    async def upsert(self, state: FolderReadStateVo) -> FolderReadState:
        existing_state = await FolderReadState.find_one(
            FolderReadState.user_id == state.user_id,
            FolderReadState.group_id == state.group_id,
        )

        if existing_state:
            existing_state.last_seen_at = state.last_seen_at
            return await existing_state.save()

        return await FolderReadState(
            id=state.id,
            user_id=state.user_id,
            group_id=state.group_id,
            last_seen_at=state.last_seen_at,
        ).insert()

    async def delete_by_group_id(self, group_id: str, session=None):
        await FolderReadState.find(FolderReadState.group_id == group_id).delete(session=session)
