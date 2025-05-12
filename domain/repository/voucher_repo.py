from abc import ABCMeta, abstractmethod
from typing import Any
from domain.voucher import Voucher as VoucherVo


class IVoucherRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, vouchers: list[VoucherVo]):
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, id):
        raise NotImplementedError

    @abstractmethod
    async def find_many(self, *filters: Any, page: int, items_per_page: int):
        raise NotImplementedError

    @abstractmethod
    async def update(self, id, file_data, file_name):
        raise NotImplementedError
