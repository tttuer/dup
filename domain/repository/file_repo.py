from abc import ABCMeta, abstractmethod
from typing import List, Any

from domain.file import File as FileVo
from infra.db_models.file import File


class IFileRepository(metaclass=ABCMeta):
    @abstractmethod
    async def save_all(self, files: List[FileVo]):
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, id: str) -> File:
        raise NotImplementedError

    @abstractmethod
    async def find_many(
        self, *filters: Any, page: int, items_per_page: int
    ) -> tuple[int, List[File]]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, id: str):
        raise NotImplementedError

    @abstractmethod
    async def delete_many(self, ids: List[str]):
        raise NotImplementedError
