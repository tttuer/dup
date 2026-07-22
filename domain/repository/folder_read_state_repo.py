from abc import ABCMeta, abstractmethod

from domain.folder_read_state import FolderReadState as FolderReadStateVo
from infra.db_models.folder_read_state import FolderReadState


class IFolderReadStateRepository(metaclass=ABCMeta):
    @abstractmethod
    async def find_by_user_and_group_ids(
        self,
        user_id: str,
        group_ids: list[str],
    ) -> list[FolderReadState]:
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, state: FolderReadStateVo) -> FolderReadState:
        raise NotImplementedError

    @abstractmethod
    async def delete_by_group_id(self, group_id: str, session=None):
        raise NotImplementedError
