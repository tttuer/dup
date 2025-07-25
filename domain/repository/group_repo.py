from abc import ABCMeta, abstractmethod
from typing import List, Any

from domain.file import Company
from domain.group import Group as GroupVo
from infra.db_models.group import Group


class IGroupRepository(metaclass=ABCMeta):
    @abstractmethod
    async def save(self, group: GroupVo):
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, id: str) -> Group:
        raise NotImplementedError

    @abstractmethod
    async def find(self, *filters: Any) -> List[Group]:
        raise NotImplementedError

    @abstractmethod
    async def find_by_name_and_company(self, name: str, company: Company) -> Group:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, id: str, session=None):
        raise NotImplementedError

    @abstractmethod
    async def update(self, group: GroupVo) -> Group:
        raise NotImplementedError
