from abc import ABCMeta, abstractmethod
from typing import List, Optional
from domain.attached_file import AttachedFile as AttachedFileVo
from infra.db_models.attached_file import AttachedFile


class IAttachedFileRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, file: AttachedFileVo) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, file_id: str) -> Optional[AttachedFile]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_request_id(self, request_id: str) -> List[AttachedFile]:
        raise NotImplementedError
    
    @abstractmethod
    async def find_by_uploader(self, uploaded_by: str) -> List[AttachedFile]:
        raise NotImplementedError
    
    @abstractmethod
    async def delete(self, file_id: str) -> None:
        raise NotImplementedError
    
    @abstractmethod
    async def delete_by_request_id(self, request_id: str) -> None:
        raise NotImplementedError