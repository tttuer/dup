from abc import ABCMeta, abstractmethod

from domain.file import File as FileVo
from infra.db_models.file import File


class IFileRepository(metaclass=ABCMeta):
    @abstractmethod
    async def save(self, file: FileVo):
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, id: str) -> File:
        raise NotImplementedError
